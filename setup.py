'''
Can be run to install all the subpieces.
'''

from __future__ import print_function
from setuptools import setup
import os
import sys
from contextlib import contextmanager

VERSION = '1.0.1'

@contextmanager
def chdir(dir):
    prev = os.getcwd()
    try:
        os.chdir(dir)
        yield
    finally:
        os.chdir(prev)

def cmd(command):
    rc = os.system(command)
    if rc != 0:
        raise OSError('"{0}" failed with return code {1}'.format(command, rc))

top_dir = os.path.dirname(os.path.abspath(__file__))

if len(sys.argv) > 1 and sys.argv[1] == 'install':
    with chdir(os.path.join(top_dir, 'gendbc')):
        print('Installing gendbc...')
        cmd('bin/activator install')

    for d in ('master_parse', 'bdc'):
        print('Installing {0}...'.format(d))
        with chdir(os.path.join(top_dir, d)):
            cmd('python setup.py install')

setup(
    name='db-build-tooling',
    package=[],
    version=VERSION,
    description='Wrapper package for Databricks Training build tools',
    author='Databricks Education Team',
    author_email='training-logins@databricks.com',
    license="Creative Commons Attribution-NonCommercial 4.0 International",
)
