#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
import re
import sys

# Can't just import gendbc, because dependencies have to be satisfied
# first. So, we'll "grep" for the VERSION.

source = "gendbc/__init__.py"

version = None
version_re = re.compile(r'''^\s*VERSION\s*=\s*['"]?([\d.]+)["']?.*$''')
with open(source) as f:
    for line in f:
        m = version_re.match(line)
        if m:
            version = m.group(1)
            break

if not version:
    sys.stderr.write("Can't find version in {0}\n".format(source))
    sys.exit(1)

setup(
    name='gendbc',
    packages=['gendbc'],
    version=version,
    description='Generate a Databricks DBC from source notebooks',
    install_requires=[
        'docopt >= 0.6.2',
        'future >= 0.16.0',
        'grizzled-python >= 1.1.0',
        'enum34 >= 1.1.6',
        'backports.tempfile >= 1.0',
        'typing >= 3.6.6',
    ],
    author='Databricks Education Team',
    author_email='training-logins@databricks.com',
    entry_points={
        'console_scripts': [
            'gendbc=gendbc:main'
        ]
    },
    classifiers=[],
)
