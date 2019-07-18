"""
Can be run to install all the subpieces.
"""

from __future__ import print_function

try:
    from setuptools import setup
    from setuptools.command.install import install
    from setuptools.command.sdist import sdist
except ImportError:
    from distutils.core import setup
    from distutils.command.install import install
    from distutils.command.sdist import sdist

from distutils.cmd import Command
import os
import sys
from contextlib import contextmanager

VERSION = '1.16.0'

@contextmanager
def chdir(dir):
    prev = os.getcwd()
    try:
        os.chdir(dir)
        yield
    finally:
        os.chdir(prev)

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


PACKAGES = [
    'bdc',
    'course',
    'db_edu_util',
    'gendbc',
    'master_parse',
]

class TestCommand(Command):
    description = 'run all tests'

    user_options = []

    def __init__(self, dist):
        Command.__init__(self, dist)


    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        run_cmd("./run-tests.sh")

setup(
    name='db-build-tooling',
    packages=PACKAGES,
    cmdclass={
        'test': TestCommand
    },
    install_requires=[
        'databricks-cli == 0.8.7',
        'docopt == 0.6.2',
        'GitPython == 2.1.11',
        'grizzled-python == 2.2.0',
        'markdown2 == 2.3.7',
        'parsimonious == 0.8.1',
        'pystache == 0.5.4',
        'PyYAML >= 5.1',
        'nbformat >= 4.4.0',
        'requests == 2.22.0',
        'termcolor >= 1.1.0',
        'WeasyPrint == 45',
    ],
    entry_points={
        'console_scripts': [
            'bdc=bdc:main',
            'course=course:main',
            'gendbc=gendbc:main',
            'master_parse=master_parse:main'
        ]
    },
    version=VERSION,
    description='Wrapper package for Databricks Training build tools',
    author='Databricks Education Team',
    author_email='training-logins@databricks.com',
    license="Creative Commons Attribution-NonCommercial 4.0 International",
)
