import asyncio
import json
import logging
import time

import boto3
import botocore
import click

from .config import Config, parse_file
from .metadata import RedisMetadataStore

_session_cache = {}
logger = logging.getLogger(__name__)


def camel_dict_to_snake_dict(camel_dict):
    """Convert Boto3 CamelCase dict to snake_case dict"""
    def camel_to_snake(name):

        import re

        first_cap_re = re.compile('(.)([A-Z][a-z]+)')
        all_cap_re = re.compile('([a-z0-9])([A-Z])')
        s1 = first_cap_re.sub(r'\1_\2', name)

        return all_cap_re.sub(r'\1_\2', s1).lower()

    def value_is_list(camel_list):

        checked_list = []
        for item in camel_list:
            if isinstance(item, dict):
                checked_list.append(camel_dict_to_snake_dict(item))
            elif isinstance(item, list):
                checked_list.append(value_is_list(item))
            else:
                checked_list.append(item)

        return checked_list

    snake_dict = {}
    for k, v in camel_dict.items():
        if isinstance(v, dict):
            snake_dict[camel_to_snake(k)] = camel_dict_to_snake_dict(v)
        elif isinstance(v, list):
            snake_dict[camel_to_snake(k)] = value_is_list(v)
        else:
            snake_dict[camel_to_snake(k)] = v

    return snake_dict


def tag_list_to_dict(tags_list):
    """Convert Boto3-style key-value tags list into dict"""
    tags_dict = {}

    for tag in tags_list:
        if 'key' in tag:
            tags_dict[tag['key']] = tag['value']
        elif 'Key' in tag:
            tags_dict[tag['Key']] = tag['Value']

    return tags_dict


def get_instance_region():
    data = {}
    fetcher = botocore.utils.InstanceMetadataFetcher()

    try:
        r = fetcher._get_request('latest/dynamic/instance-identity/document', fetcher._needs_retry_for_credentials)
        data = json.loads(r.text)
    except botocore.utils._RetriesExceededError:
        logger.warn(f'Max number of attempts exceeded ({fetcher._num_attempts}) when attempting to retrieve region from metadata service.')

    return data.get('region', None)


def get_session(config):
    if config.profile_name not in _session_cache:
        logger.info(f'Creating new Boto3 Session for profile {config.profile_name}')
        _session_cache[config.profile_name] = boto3.Session(profile_name=config.profile_name)

    session = _session_cache[config.profile_name]

    if config.role_arn:
        if config.role_arn not in _session_cache:
            sts_client = session.client('sts')
            role_session_name = f'{__name__}.session-{time.time()}'

            logger.info(f'Assuming role {config.role_arn}')
            assumed_role = sts_client.assume_role(RoleArn=config.role_arn,
                                                  ExternalId=config.external_id,
                                                  RoleSessionName=role_session_name)
            logger.info(f'Creating new Boto3 Session for role {config.role_arn}')
            _session_cache[config.role_arn] = boto3.Session(aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
                                                            aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
                                                            aws_session_token=assumed_role['Credentials']['SessionToken'])

        session = _session_cache[config.role_arn]

    return session


async def store_aws_metadata(config):
    """Store AWS metadata (result of ec2.describe_instances call) into Redis"""
    try:
        session = get_session(config)
    except botocore.exceptions.ClientError as e:
        logger.error(f'Unable to get Boto3 Session: {e}')
        raise SystemExit(1)

    regions = [config.region_name or session.region_name or get_instance_region()]

    if 'all' in regions:
        regions = session.get_available_regions('ec2')

    async with RedisMetadataStore(config) as metadata:
        for region in regions:
            logger.info(f'Describing instances in {region}')
            try:
                ec2_client = session.client('ec2', region)
            except Exception as e:
                logger.error(f'Failed to create EC2 client: {e}')
                return

            # Find all instances, convert to snake dict, convert to tags, store in redis
            try:
                instances = ec2_client.describe_instances()
                for reservation in instances.get('Reservations', []):
                    for instance in reservation.get('Instances', []):
                        instance = camel_dict_to_snake_dict(instance)
                        instance['tags'] = tag_list_to_dict(instance.get('tags', []))
                        logger.info(f'Storing data for {instance["instance_id"]}')
                        await metadata.store_instance(instance)
            except Exception as e:
                logger.error(f'Failed to sync instance information: {e}')
                return

            try:
                interfaces = ec2_client.describe_network_interfaces()
                for interface in interfaces.get('NetworkInterfaces', []):
                    interface = camel_dict_to_snake_dict(interface)
                    interface['tags'] = tag_list_to_dict(interface.pop('tag_set', []))
                    logger.info(f'Storing data for {interface["network_interface_id"]}')
                    await metadata.store_interface(interface)
            except Exception as e:
                logger.error(f'Failed to sync interface information: {e}')
                return


@click.option(
    '--debug',
    is_flag=True,
    help="Enable debug logging to STDERR."
)
@click.option(
    '--ttl',
    default=1800,
    type=int,
    help='Time-to-live for AWS metadata stored in Redis.')
@click.option(
    '--port',
    default=6379,
    type=int,
    help='Redis server port.'
)
@click.option(
    '--host',
    default='localhost',
    type=str,
    help='Redis server hostname.'
)
@click.option(
    '--external-id',
    default=None,
    type=str,
    help='A unique identifier that is used by third parties when assuming roles in their customers\' accounts.'
)
@click.option(
    '--role-arn',
    default=None,
    type=str,
    help='The Amazon Resource Name (ARN) of the role to assume.'
)
@click.option(
    '--region',
    default=None,
    type=str,
    help='AWS Region name (overrides region from profile).'
)
@click.option(
    '--profile',
    default=None,
    type=str,
    help='AWS Configuration Profile name.'
)
@click.command(short_help='Collect EC2 inventory and store to Redis.')
def sync(**args):
    loop = asyncio.get_event_loop()
    sync_config = Config(**args)

    if sync_config.debug_enabled:
        logging.basicConfig(level='DEBUG')
        loop.set_debug(1)
    else:
        logging.basicConfig(level='INFO', format='%(message)s')

    loop.run_until_complete(store_aws_metadata(sync_config))
    loop.close()


@click.option(
    '--debug',
    is_flag=True,
    help="Enable debug logging to STDERR."
)
@click.option(
    '--config',
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help='Path to configuration file describing accounts and regions to sync.'
)
@click.command('sync-multi', short_help='Collect EC2 inventory from multiple accounts.')
def sync_multi(debug, config):
    loop = asyncio.get_event_loop()

    if debug:
        logging.basicConfig(level='DEBUG')
        loop.set_debug(1)
    else:
        logging.basicConfig(level='INFO', format='%(message)s')

    for sync_config in parse_file(config):
        loop.run_until_complete(store_aws_metadata(sync_config))

    loop.close()
