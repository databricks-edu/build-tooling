#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
import re
import sys

# Can't just import course, because dependencies have to be satisfied
# first. So, we'll "grep" for the VERSION.

source = "course/__init__.py"

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
    name='course',
    packages=['course'],
    version=version,
    description='Workflow management tool for Databricks curriculum development',
    install_requires=[
        'future >= 0.16.0',
        'markdown2 >= 2.3.5',
        'backports.tempfile >= 1.0',
        'termcolor >= 1.1.0',
    ],
    author='Databricks Education Team',
    author_email='training-logins@databricks.com',
    entry_points={
        'console_scripts': [
            'course=course:main'
        ]
    },
    classifiers=[],
)
