AWS ACL Helper
==============

This module implements the Squid External ACL Helper interface, and
allows for use of EC2 instance metadata in ACL entries. It uses the
client's source address (either public or private) as a key to determine
which instance initiated a request through the proxy, and allows use of
instance metadata (such as Instance ID, VPC, or Security Group
membership) as a rule target.

If the request can be mapped to an EC2 instance, the module will
populate the EC2 Instance ID into the request's 'user' field, for
consumption by additional ACLs or output to logs. This occurs regardless
of whether or not the ACL matched.

Prerequisites
-------------

This module requires Python 3.4 or better, due to its use of the
``asyncio`` framework (``aioredis``, etc)

This module requires a Redis server to cache AWS instance metadata.
Redis clusters are not currently supported; use of a local Redis
instance is recommended.

This module uses Boto3 to retrieve EC2 instance metadata from AWS. You
should have a working AWS API environment (~/.aws/credentials,
environment variables, or EC2 IAM Role) that allows calling EC2's
``describe-instances`` method against the account that Squid is running
in. If using EC2 IAM Roles, you should use the ``--region`` option or
``AWS_DEFAULT_REGION`` environment variable to specify a region.

Consult `README.md on GitHub <https://github.com/brandond/aws-acl-helper/blob/master/README.md>`__ for usage instructions.
