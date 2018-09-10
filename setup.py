# -*- coding: utf-8 -*-
import sys
from os import chdir
from os.path import abspath, dirname

from setuptools import find_packages, setup

chdir(dirname(abspath(__file__)))

if sys.version_info < (3, 5):
    raise RuntimeError("aws-acl-helper doesn't support Python versions below 3.5")

with open('README.rst') as f:
    readme = f.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    author='Brandon Davidson',
    author_email='brad@oatmail.org',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: No Input/Output (Daemon)',
        'Framework :: AsyncIO',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: Security',
    ],
    description='Squid external ACL helper that allows use of AWS instance metadata',
    entry_points={
        'console_scripts': ['aws-acl-helper=aws_acl_helper.commands:cli']
    },
    include_package_data=True,
    install_requires=requirements,
    long_description=readme,
    name='aws-acl-helper',
    packages=find_packages(exclude=('docs')),
    python_requires='>=3.5',
    url='https://github.com/brandond/aws-acl-helper',
    version_command=('git describe --tags --dirty', 'pep440-git-full'),
)
