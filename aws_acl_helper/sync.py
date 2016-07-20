import click
import boto3
import asyncio

from . import metadata
from . import config

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


def store_aws_metadata(config):
    """Store AWS metadata (result of ec2.describe_instances call) into Redis"""
    loop = asyncio.get_event_loop()
    session = boto3.Session(profile_name=config.profile_name, region_name=config.region_name)
    client = session.client('ec2')
    response = client.describe_instances()
    tasks = []

    # Find all instances, convert to snake dict, convert to tags, and fire off
    # task to store in Redis
    for reservation in response.get('Reservations', []):
        for instance in reservation.get('Instances', []):
            instance = camel_dict_to_snake_dict(instance)
            instance['tags'] = tag_list_to_dict(instance.get('tags', []))
            print('Storing data for {instance_id}'.format(**instance))
            tasks.append(loop.create_task(metadata.store(config,instance)))

    if len(tasks) > 0: 
        loop.run_until_complete(asyncio.wait(tasks))
        loop.stop()

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
@click.command()
def sync(**args):
    """Collect inventory from EC2 and persist to Redis"""
    _config = config.Config(**args)
    store_aws_metadata(_config)

