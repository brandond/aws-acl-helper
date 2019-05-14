import asyncio
import fnmatch


@asyncio.coroutine
def test(request, metadata):
    """Return an ACL action (OK, ERR, or BH) by comparing ACL entries against host metadata"""

    if not request.client:
        return 'BH', {'log': 'Failed to parse client IP address'}
    if not metadata:
        return 'ERR', {'log': 'Metadata not available for this client'}
    else:
        for entry in request.acl:
            if check_acl_entry(entry, metadata):
                return 'OK', get_user(metadata)
        return 'ERR', get_user(metadata)


def get_user(metadata):
    user = None
    for key in 'instance_id', 'network_interface_id':
        if key in metadata:
            user = metadata[key]

    if user:
        name = None
        if 'tags' in metadata and 'Name' in metadata['tags']:
            name = metadata['tags']['Name']
        elif 'description' in metadata:
            name = metadata['description']

        if name:
            user = f'{user} ({name})'

        return {'user': user}
    else:
        return {}


def check_acl_entry(entry, metadata):
    """ Check an individual ACL entry against host metadata

    Returns True if matched, else False

    Supported ACL entry strings:
        * Instance ID (i-xxx)
        * Security Group ID (sg-xxx)
        * Image AMI ID (ami-xxx)
        * VPC ID (vpc-xxx)
        * Subnet ID (subnet-xxx)
        * Availability zone (az:us-west-2*)          - Matches shell-style globs
        * Security Group Name (sg:my security group) - Matches shell-style globs
        * Tag (tag:Name=Value)                       - Matches shell-style globs
        * Existence as an EC2 instance (any)         - Matches if request is from a known EC2 instance
    """

    if entry.startswith('i-'):
        return entry == metadata.get('instance_id', None)

    elif entry.startswith('eni-'):
        for interface in get_interfaces(metadata):
            if entry == interface.get('network_interface_id'):
                return True
        return False

    elif entry.startswith('sg-'):
        for interface in get_interfaces(metadata):
            for group in interface.get('groups', []):
                if entry == group.get('group_id'):
                    return True
        return False

    elif entry.startswith('ami-'):
        return entry == metadata.get('image_id', None)

    elif entry.startswith('vpc-'):
        return entry == metadata.get('vpc_id', None)

    elif entry.startswith('subnet-'):
        for interface in get_interfaces(metadata):
            if entry == interface.get('subnet_id'):
                return True
        return False

    elif entry.startswith('owner:'):
        owner_id = entry[6:].lower()
        for interface in get_interfaces(metadata):
            if owner_id == interface.get('owner_id'):
                return True
        return False

    elif entry.startswith('az:'):
        pattern = entry[3:].lower()
        return fnmatch.fnmatch(metadata.get('placement', {}).get('availability_zone', '').lower(), pattern)

    elif entry.startswith('sg:'):
        pattern = entry[3:].lower()
        for interface in get_interfaces(metadata):
            for group in interface.get('groups', []):
                if fnmatch.fnmatch(group.get('group_name', '').lower(), pattern):
                    return True
        return False

    elif entry.startswith('tag:'):
        pattern = entry[4:]
        key, pattern = pattern.split('=', 1)
        pattern = pattern.lower()
        if key in metadata.get('tags', {}):
            if fnmatch.fnmatch(metadata['tags'][key].lower(), pattern):
                return True
        return False

    elif entry.startswith('type:'):
        meta_type = entry[5:].lower()
        if meta_type == 'ec2':
            return 'instance_id' in metadata
        elif meta_type == 'lambda':
            return metadata.get('attachment', {}).get('instance_owner_id', None) == 'aws-lambda'
        else:
            return False

    elif entry == 'any':
        return True

    else:
        return False


def get_interfaces(metadata):
    if 'instance_id' in metadata:
        return metadata.get('network_interfaces', [])
    elif 'network_interface_id' in metadata:
        return [metadata]
    else:
        return []
