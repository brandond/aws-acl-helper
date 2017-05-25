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
against the account that Squid is running in.

Getting Started
---------------

1. **Install aws-acl-helper:**

   `pip install aws-acl-helper`

2. **Retrieve EC2 instance metadata from AWS and store in Redis:**
 
    `aws-acl-helper sync --region us-west-2`

    By default, metadata expires from Redis after 30 minutes. This is intended
    to ensure that ACLs are not applied to the wrong hosts. Adjust the TTL up
    or down depending on the volatility of your environment.

    **Note**: You should probably schedule this at regular intervals, (with a
    cronjob, etc) as ACLs will not match hosts that exist in EC2 but have not
    yet been sync'd into Redis.

3. **Configure external ACL helper in Squid:**

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
 * Owner ID (`owner:012345678901`)              **- 12-digit AWS Account ID**
 * Availability Zone (`az:us-west-2*`)          **- Supports shell-style globs**
 * Security Group Name (`sg:my security group`) **- Supports shell-style globs**
 * Tag (`tag:Name=Value`)                       **- Supports shell-style globs**
 * Metadata availability (`any`)                **- Matches if request is from any known EC2 instance**

Usage
-----

Run against a single account with options specified on the command line:

```
Usage: aws-acl-helper sync [OPTIONS]

Options:
  --profile TEXT      AWS Configuration Profile name.
  --region TEXT       AWS Region name (overrides region from profile).
  --role-arn TEXT     The Amazon Resource Name (ARN) of the role to assume.
  --external-id TEXT  A unique identifier that is used by third parties when
                      assuming roles in their customers' accounts.
  --host TEXT         Redis server hostname.
  --port INTEGER      Redis server port.
  --ttl INTEGER       Time-to-live for AWS metadata stored in Redis.
  --help              Show this message and exit.
```

Run against one or more accounts using a config file:

```
Usage: aws-acl-helper sync-multi [OPTIONS]

Options:
  --config PATH  Path to configuration file describing accounts and regions to
                 sync.  [required]
  --help         Show this message and exit.
```

Configuration File Syntax
-------------------------

The configuration file used by the `sync-multi` command should be in standard ConfigParser INI format.
Specify one section per account; other than the DEFAULT section; section names are not important.
Options are the same as those available to the `sync` command:

| Key         | Type    | Description |
| -           | -       | - |
| profile     | TEXT    | AWS Configuration Profile name. |
| region      | TEXT    | AWS Region name (overrides region from profile or environment). |
| role_arn    | TEXT    | The Amazon Resource Name (ARN) of the role to assume. |
| external_id | TEXT    | A unique identifier that is used by third parties when assuming roles in their customers' accounts. |
| host        | TEXT    | Redis server hostname. |
| port        | INTEGER | Redis server port. |
| ttl         | INTEGER | Time-to-live for AWS metadata stored in Redis. |

Sample Configuration File:

```
[DEFAULT]
host = localhost
port = 6379
ttl = 1800

[management]
# no configuration necessary; use IAM Role Credentials for current account

[development]
role_arn = arn:aws:iam::111111111111:role/dev-acl-helper-role
external_id = 123

[uat]
role_arn = arn:aws:iam::222222222222:role/uat-acl-helper-role
external_id = 456

```

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

   In order to reference security groups or tag values that contain spaces, the
   [configuration_includes_quoted_values](http://www.squid-cache.org/Doc/config/configuration_includes_quoted_values/)
   option must be toggled on prior to the quoted ACL definition. The option can
   be toggled back off afterwards.
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
available at [docs/create-virtualenv.sh](docs/create-virtualenv.sh).

These issues seem to be resolved with Python 3.5, which I recommend using if at all possible.
