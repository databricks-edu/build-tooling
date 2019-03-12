#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
from distutils.cmd import Command
import re
import sys
import os

# Can't just import notebooktools, because dependencies have to be satisfied
# first. So, we'll "grep" for the VERSION.

source = "db_edu_util/__init__.py"

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

class Test(Command):
    description = 'run the Nose tests'

    user_options = []

    def __init__(self, dist):
        Command.__init__(self, dist)

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # Convention: Run the module to run the tests.
        for module_path in ('db_cli.py',):
            p = os.path.join('db_edu_util', module_path)
            run_cmd('python ' + p)

setup(
    name='db_edu_util',
    packages=['db_edu_util'],
    version=version,
    description='Library of stuff used by the build tools',
    install_requires=[
    ],
    cmdclass = {
        'test': Test
    },
    author='Databricks Education Team',
    author_email='training-logins@databricks.com',
    classifiers=[],
)
