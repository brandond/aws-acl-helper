import click
import boto3
import asyncio

from . import metadata

def camel_dict_to_snake_dict(camel_dict):

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
    tags_dict = {}

    for tag in tags_list:
        if 'key' in tag:
            tags_dict[tag['key']] = tag['value']
        elif 'Key' in tag:
            tags_dict[tag['Key']] = tag['Value']

    return tags_dict


def store_all_metadata():
    loop = asyncio.get_event_loop()
    client = boto3.client('ec2')
    response = client.describe_instances()
    tasks = []

    for reservation in response.get('Reservations', []):
        for instance in reservation.get('Instances', []):
            instance = camel_dict_to_snake_dict(instance)
            instance['tags'] = tag_list_to_dict(instance.get('tags', []))
            print('Storing data for {instance_id}'.format(**instance))
            tasks.append(loop.create_task(metadata.store(instance)))
    
    loop.run_until_complete(asyncio.wait(tasks))
    loop.stop()

@click.command()
def sync():
    store_all_metadata()


