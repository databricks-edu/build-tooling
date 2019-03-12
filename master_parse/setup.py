#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
from distutils.cmd import Command
import re
import sys

# Can't just import master_parse, because dependencies have to be satisfied
# first. So, we'll "grep" for the VERSION.

source = "master_parse/__init__.py"

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

def run_cmd(command_string):
    import subprocess
    try:
        print(f'+ {command_string}')
        rc = subprocess.call(command_string, shell=True)
        if rc < 0:
            print(f'Command terminated by signal {-rc}',
                  file=sys.stderr)
    except OSError as e:
        print(f'Command failed: {e}', file=sys.stderr)

setup(
    name='master_parse',
    packages=['master_parse'],
    version=version,
    description='Master parse tool',
    install_requires=[
        'pystache == 0.5.4',
        'nbformat==4.4.0',
    ],
    author='Databricks Education Team',
    author_email='training-logins@databricks.com',
    license="Creative Commons Attribution-NonCommercial 4.0 International",
    entry_points={
        'console_scripts': [
            'master_parse=master_parse:main'
        ]
    },
    classifiers=[],
)
