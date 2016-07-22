#!/bin/bash -e
# This script requires a working Python 3.4 install and build environment, including:
# autoconf automake gcc git openssl-devel libffi-devel python34 python34-devel libxml2-devel libxslt-devel

TARGET="$1"

if [ "${TARGET}" == "" ]; then
  TARGET="/opt/python34-env"
fi

mkdir -p "${TARGET}"

# Set up Python 3.4 virtual environment
virtualenv --python=/usr/bin/python3.4 --clear --no-pip --no-setuptools "${TARGET}"
if grep -q 'Amazon Linux' /etc/system-release; then
  # Amazon Linux has something weird set up with dist-packages, so hack that with a symlink
  ln -sf site-packages "${TARGET}/lib64/python3.4/dist-packages"
fi

# bootstrap pip/wheel/setuptools since dist-packaged Python 3.4 tends to come broken
source "${TARGET}/bin/activate"
curl -s https://bootstrap.pypa.io/get-pip.py | python

# Install important Python 3.4 packages
pip install --upgrade git+https://github.com/aio-libs/aioredis
pip install --upgrade git+https://github.com/brandond/aws-acl-helper
