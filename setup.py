'''
Can be run to install all the subpieces.
'''

from __future__ import print_function
import os
import sys
from contextlib import contextmanager

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

with chdir(os.path.join(top_dir, 'gendbc')):
    print('Installing gendbc...')
    cmd('bin/activator install')

for d in ('master_parse', 'bdc'):
    print('Installing {0}...'.format(d))
    with chdir(os.path.join(top_dir, d)):
        cmd('python setup.py install')

sys.exit(0)
