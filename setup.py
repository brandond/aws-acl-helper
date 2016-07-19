# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

version = {}
with open("aws_acl_helper/version.py") as fp:
    exec(fp.read(), version)

setup(
    name='aws-acl-helper',
    version=version,
    description='Squid external ACL helper that allows use of AWS instance metadata',
    long_description=readme,
    author='Brandon Davidson',
    author_email='brad@oatmail.org',
    url='https://github.com/brandond/aws-acl-helper',
    download_url='https://github.com/brandond/aws-acl-helper/tarball/{}'.format(version)
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),
    entry_points={
        'console_scripts': ['aws-acl-helper=aws_acl_helper.commands:cli']
    },
    include_package_data=True,
)

