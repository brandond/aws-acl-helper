# -*- coding: utf-8 -*-

import sys
from setuptools import setup, find_packages

if sys.version_info < (3, 4):
    raise RuntimeError("aws-acl-helper doesn't support Python versions below 3.4")

version = {}

with open("aws_acl_helper/version.py") as fp:
    exec(fp.read(), version)

with open('README.rst') as f:
    readme = f.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='aws-acl-helper',
    version=version['__version__'],
    description='Squid external ACL helper that allows use of AWS instance metadata',
    long_description=readme,
    author='Brandon Davidson',
    author_email='brad@oatmail.org',
    url='https://github.com/brandond/aws-acl-helper',
    download_url='https://github.com/brandond/aws-acl-helper/tarball/{}'.format(version['__version__']),
    license='Apache',
    packages=find_packages(exclude=('docs')),
    entry_points={
        'console_scripts': ['aws-acl-helper=aws_acl_helper.commands:cli']
    },
    include_package_data=True,
    install_requires=requirements,
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: Proxy Servers',
    ],

)
