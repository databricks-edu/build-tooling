'''
Can be run to install all the subpieces.
'''

from __future__ import print_function

try:
    from setuptools import setup
    from setuptools.command.install import install
    from setuptools.command.sdist import sdist
except ImportError:
    from distutils.core import setup
    from distutils.command.install import install
    from distutils.command.sdist import sdist

import os
import sys
from contextlib import contextmanager

VERSION = '1.10.1'

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

class CustomInstallCommand(install):
    """Customized setuptools install command - prints a friendly greeting."""
    def run(self):
        install.run(self)


top_dir = os.path.dirname(os.path.abspath(__file__))

if (len(sys.argv) > 1 and
    (sys.argv[1] == 'install') or (sys.argv[1].startswith('bdist'))):
    print('Installing/upgrading databricks-cli')
    cmd('pip install --upgrade databricks-cli')

    for d in ('master_parse', 'bdc', 'gendbc', 'course'):
        print('Installing {0}...'.format(d))
        with chdir(os.path.join(top_dir, d)):
            cmd('python setup.py install')

setup(
    name='db-build-tooling',
    packages=[],
    install_requires=[
        'databricks-cli==0.8.0',
    ],
    version=VERSION,
    description='Wrapper package for Databricks Training build tools',
    author='Databricks Education Team',
    author_email='training-logins@databricks.com',
    license="Creative Commons Attribution-NonCommercial 4.0 International",
)
