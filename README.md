AWS ACL Helper
==============

This module implements the Squid External ACL Helper interface, and allows for
use of EC2 instance metadata in ACL entries. It uses the client's source
address (either public or private) as a key to determine which instance 
initiated a request through the proxy, and allows use of instance metadata
(such as Instance ID, VPC, or Security Group membership) as a rule target.

If the request can be mapped to an EC2 instance, the module will populate
the EC2 Instance ID into the request's 'user' field, for consumption by
additional ACLs or output to logs. This occurs regardless of whether or not
the ACL matched.

Prerequisites
-------------

This module requires Python 3.4 or better, due to its use of the `asyncio`
framework (`aioredis`, etc)

This module requires a Redis server to cache AWS instance metadata. Redis 
clusters are not currently supported; use of a local Redis instance is
recommended.

This module uses Boto3 to retrieve EC2 instance metadata from AWS. You should 
have a working AWS API environment (~/.aws/credentials, environment variables,
or EC2 IAM Role) that allows calling EC2's `describe-instances` method
against the account that Squid is running in. If using EC2 IAM Roles, you 
should use the `--region` option or `AWS_DEFAULT_REGION` environment variable
to specify a region.

Usage
-----

1. **Retrieve EC2 instance metadata from AWS and store in Redis:**

   `aws-acl-helper sync --region us-west-2`

    By default, metadata expires from Redis after 30 minutes. This is intended
    to ensure that ACLs are not applied to the wrong hosts. Adjust the TTL up
    or down depending on the volatility of your environment.

    **Note**: You should probably schedule this at regular intervals, (with a
    cronjob, etc) as ACLs will not match hosts that exist in EC2 but have not
    yet been sync'd into Redis.

2. **Configure external ACL helper in Squid:**

    In your Squid config, define the external ACL, and apply some rules that
    use it:
    ```
    # Define external ACL helper
    external_acl_type ec2 ttl=60 children-startup=1 children-idle=1 children-max=4 concurrency=1000 ipv4 %SRC /path/to/aws-acl-helper listen
    
    # Simple Example:
    #
    # Define an ACL that matches a security group and an instance by ID.
    acl ec2_google_ok external ec2 sg-xxxxxxxx i-yyyyyyyy

    # Complex Example:
    #
    # Define a pair of ACLs that match a security group by name in a specific VPC.
    # Since security group names are not unique across VPCs, a separate ACL must be used
    # to match the VPC ID.
    configuration_includes_quoted_values on
    acl ec2_vpc_zzzzzzzz external ec2 vpc-zzzzzzzz
    acl ec2_github_ok external ec2 "sg:github access security group"
    configuration_includes_quoted_values off
    
    # Define ACLs for traffic to various domains
    acl to_google dstdomain -n .google.com
    acl to_github dstdomain -n .github.com
    
    # Allow requests matching ACLs
    http_access allow ec2_google_ok to_google
    http_access allow ec2_vpc_zzzzzzzz ec2_github_ok to_github
    
    # Deny everything else
    http_access deny
    ```
    
Supported ACL Parameters
------------------------
 * Instance ID (`i-xxx`)
 * Security Group ID `(sg-xxx`)
 * Image AMI ID (`ami-xxx`)
 * VPC ID (`vpc-xxx`)
 * Subnet ID (`subnet-xxx`)
 * Availability Zone (`az:us-west-2*`)          **- Supports shell-style globs**
 * Security Group Name (`sg:my security group`) **- Supports shell-style globs**
 * Tag (`tag:Name=Value`)                       **- Supports shell-style globs**
 * Metadata availability (`any`)                **- Matches if request is from any known EC2 instance**

Caveats
-------
1. **ACL Definitions May Not Span Multiple Lines**

    Unlike built-in ACL types, external ACLs cannot span multiple lines.
    All parameters for a given ACL must be specified on a single line.

    Works:
    ```
    acl my_acl external ec2 sg-xxxxxxxx sg-yyyyyyyy
    ```

    Does Not Work:
    ```
    acl my_acl external ec2 sg-xxxxxxxx
    acl my_acl external ec2 sg-yyyyyyyy
    ```

2. **Parameters Containing Spaces Must Be Quoted or Encoded**

   In order to reference security groups or tag values that contain spaces,
   the `configuration_includes_quoted_values` option must be toggled off prior
   to the quoted ACL definition. The option can be toggled back on afterwards.
   ```
   configuration_includes_quoted_values on
   acl my_acl external ec2 "sg:my security group name"
   configuration_includes_quoted_values off
   ```

   Alternately, you could place your ACL parameters in an external file, one
   per line, and use the quoted inclusion feature:
   ```
   acl my_acl external ec2 "/path/to/acl_parameters.txt"
   ```

Use With Amazon Linux
---------------------
Setting up a Python 3.4 virtualenv in RedHat based distributions can be
difficult, since they do some weird things with packaging pip and setuptools.
A script to automate the build of a virtualenv containing this module is
available at [docs/create-virtualenv.sh](docs/create-virtualenv.sh)
