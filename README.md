AWS ACL Helper
==============
This module implements the Squid External ACL Helper interface, and allows for use of EC2 instance metadata
in ACL entries. It uses the client's source address (either public or private) as a key to determine which
instance initiated a request through the proxy, and allows use of instance metadata (such as Instance ID, VPC, 
or Security Group membership) as a rule target.

Prerequisites
-------------
This module requires a Redis server to cache AWS instance metadata. Redis clusters are not currently supported.

This module uses Boto3 to retrieve EC2 instance metadata from AWS. You should have a working AWS API
environment (~/.aws/credentials, environment variables, or instance profile) that allows calling EC2's
```describe-instances``` method.

Usage
-----

1. **Retrieve EC2 instance metadata from AWS and store in Redis:**
   ```aws-acl-helper sync```

    By default, metadata expires from Redis after 30 minutes. This is intended
    to ensure that ACLs are not applied to the wrong hosts. Adjust the TTL up or down
    depending on the volatility of your environment.

    **Note**: You should probably schedule this at regular intervals, (with a cronjob, etc)
    as ACLs will not match hosts that exist in EC2 but have not yet been sync'd into Redis.

2. **Configure external ACL helper in Squid:**

    In your Squid config, define the external ACL, and apply some rules that use it:
    ```
    # Define external ACL helper
    external_acl_type ec2 ttl=60 children-startup=1 children-idle=1 children-max=4 concurrency=1000 ipv4 >a /path/to/aws-acl-helper listen
    
    # Define an ACL that matches a security group and an instance
    acl ec2_google_ok ec2 sg-xxxxxxxx
    acl ec2_google_ok ec2 i-yyyyyyyy
    
    # Define an ACL that allows requests to Google
    acl to_google dstdomain .google.com
    
    # Allow requests matching both ACLs
    http_access allow ec2_google_ok to_google
    
    # Deny everything else
    http_access deny
    ```
    
Supported ACL Entry Keys
------------------------
 * Instance ID (`i-xxx`)
* Security Group ID `(sg-xxx`)
* Image AMI ID (`ami-xxx`)
* VPC ID (`vpc-xxx`)
* Subnet ID (`subnet-xxx`)
* Availability zone (`az:us-west-2*`)          **- Matches shell-style globs**
* Security Group Name (`sg:my security group`) **- Matches shell-style globs**
* Tag (`tag:Name=Value`)                       **- Matches shell-style globs**
* Existence as an EC2 instance (`ec2`)         **- Matches if request is from a known EC2 instance**
