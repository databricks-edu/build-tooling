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

VERSION = '1.13.0'

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
        for module_path in ('bdc', 'master_parse', 'db_edu_util',):
            with chdir(module_path):
                print('\nRunning tests in ' + module_path)
                run_cmd('python setup.py test')


setup(
    name='db-build-tooling',
    packages=[],
    install_requires=[
    ],
    cmdclass = {
        'test': Test
    },
    version=VERSION,
    description='Wrapper package for Databricks Training build tools',
    author='Databricks Education Team',
    author_email='training-logins@databricks.com',
    license="Creative Commons Attribution-NonCommercial 4.0 International",
)


top_dir = os.path.dirname(os.path.abspath(__file__))

if (len(sys.argv) > 1 and
    (sys.argv[1] == 'install') or (sys.argv[1].startswith('bdist'))):
    print('Installing/upgrading databricks-cli')
    run_cmd('pip install --upgrade databricks-cli')

    for d in ('db_edu_util', 'master_parse', 'bdc', 'gendbc', 'course'):
        print('Installing {0}...'.format(d))
        with chdir(os.path.join(top_dir, d)):
            run_cmd('python setup.py install')
