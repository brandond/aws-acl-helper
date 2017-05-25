import asyncio
import fnmatch

from . import squid


@asyncio.coroutine
def test(request, metadata):
    """Return an ACL action (OK, ERR, or BH) by comparing ACL entries against host metadata"""

    if request.client is None:
        return 'BH', {'log': 'Failed to parse client IP address'}
    if metadata is None or 'instance_id' not in metadata:
        return 'ERR', {'log': 'Metadata not available for this client'}
    else:
        for entry in request.acl:
            if check_acl_entry(entry, metadata):
                return 'OK', {'user': metadata['instance_id']}
        return 'ERR', {'user': metadata['instance_id']}


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
        return entry == metadata.get('instance_id')

    elif entry.startswith('sg-'):
        for interface in metadata.get('network_interfaces', []):
            for group in interface.get('groups', []):
                if entry == group.get('group_id'):
                    return True
        return False

    elif entry.startswith('ami-'):
        return entry == metadata.get('image_id')

    elif entry.startswith('vpc-'):
        return entry == metadata.get('vpc_id')

    elif entry.startswith('subnet-'):
        for interface in metadata.get('network_interfaces', []):
            if entry == interface.get('subnet_id'):
                return True
        return False

    elif entry.startswith('owner:'):
        owner_id = entry[6:].lower()
        for interface in metadata.get('network_interfaces', []):
            if owner_id == interface.get('owner_id'):
                return True
        return False

    elif entry.startswith('az:'):
        pattern = entry[3:].lower()
        return fnmatch.fnmatch(metadata.get('placement', {}).get('availability_zone', '').lower(), pattern)

    elif entry.startswith('sg:'):
        pattern = entry[3:].lower()
        for interface in metadata.get('network_interfaces', []):
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

    elif entry == 'any':
        return True

    else:
        return False
