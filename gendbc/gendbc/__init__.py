"""
Tool and library to generate a DBC from a series of source notebooks found
under a source directory.

To see the command line usage, run "gendbc -h".

To use the library interface, see the gendbc() function.
"""

import os
import sys
import docopt
import traceback
from textwrap import TextWrapper
from typing import Sequence
from collections import namedtuple
import codecs
from backports.tempfile import TemporaryDirectory
import shutil
from zipfile import ZipFile

from future import standard_library
standard_library.install_aliases()

from nbtools import *

__all__ = ['Config', 'GendbcError', 'gendbc']

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

VERSION = "2.0.1"

PROG = os.path.basename(sys.argv[0])

USAGE = ('''
{0}, version {2}

Usage:
  {0} [-D | --debug]
  {1} [-e ENC | --encoding ENC]
  {1} [-f FOLDER | --folder FOLDER]
  {1} [--flatten]
  {1} [-h | --help]
  {1} [-s | --stack]
  {1} [-v | --verbose] SRCDIR DBC

  {0} (-V | --version)
  
Options:
  -D, --debug                 Emit debug messages
  -e ENC, --encoding ENC      Encoding of the input notebooks. [default: UTF-8]
  -f FOLDER, --folder FOLDER  Top-level folder in the generated DBC, if any
  --flatten                   Flatten the DBC, putting all files in the top
                              folder (if --folder is specified) or at the top
                              of the DBC (if not).
  -h, --help                  This message
  -s, --stack                 Show stack traces on error.
  -v, --verbose               Emit verbose messages
  -V, --version               Show version and exit
  
SRCDIR is the source directory containing the notebooks. It is scanned
recursively.

DBC is the path to the DBC file to generate.
'''.format(PROG, ' ' * len(PROG), VERSION))

COLUMNS = int(os.getenv('COLUMNS', '80')) - 1
WARNING_PREFIX = "*** WARNING: "
DEBUG_PREFIX = "(DEBUG) "
ERROR_PREFIX = "ERROR: "

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

Config = namedtuple('Config', ('debug', 'verbose', 'encoding', 'dbc_folder',
                               'flatten', 'show_stack', 'source_dir', 'dbc'))

class GendbcError(Exception):
    def __init__(self, msg=''):
        Exception.__init__(self, msg)


class UsageError(Exception):
    def __init__(self, msg=''):
        Exception.__init__(self, msg)


class LocalTextWrapper(TextWrapper):
    def __init__(self, width=COLUMNS, subsequent_indent=''):
        TextWrapper.__init__(self,
                             width=width,
                             subsequent_indent=subsequent_indent)

    def fill(self, msg):
        wrapped = [TextWrapper.fill(self, line) for line in msg.split('\n')]
        return '\n'.join(wrapped)



# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------

_be_verbose = False

_warning_wrapper = LocalTextWrapper(subsequent_indent=' ' * len(WARNING_PREFIX))
_debug_wrapper = LocalTextWrapper(subsequent_indent=' ' * len(DEBUG_PREFIX))
_error_wrapper = LocalTextWrapper(subsequent_indent=' ' * len(ERROR_PREFIX))
_verbose_prefix = os.path.basename(sys.argv[0]) + ': '
_verbose_wrapper = LocalTextWrapper(subsequent_indent=' ' * len(_verbose_prefix))

# -----------------------------------------------------------------------------
# Internal functions
# -----------------------------------------------------------------------------

def _printerr(msg):
    # type: (str) -> None
    """
    Print a message to standard error, automatically adding a newline.
    Does not wrap the message.

    :param msg: the message.
    :return: nothing
    """
    sys.stderr.write(msg + '\n')


def _die(msg):
    # type: (str) -> None
    """
    Print a message to standard error, automatically adding a newline. Then,
    abort the program with an exit code of 1.

    :param msg: the message.
    :return: doesn't.
    """
    _printerr(msg)
    sys.exit(1)

def _verbose(msg):
    # type: (str) -> None
    """
    Print a verbose message, if verbosity is enabled. Otherwise, do nothing.

    :param msg: the message.
    :return: nothing
    """
    if _be_verbose:
        print(_verbose_wrapper.fill(_verbose_prefix + msg))


def _error(msg):
    # type: (str) -> None
    """
    Print a message to standard error, with an error prefix, automatically
    adding a newline and wrapping the message.

    :param msg: the message.
    :return: nothing
    """
    _printerr(_error_wrapper.fill("{}{}".format(ERROR_PREFIX, msg)))


def _debug(msg):
    # type: (str) -> None
    """
    Print a debug message to standard output, with a debug prefix,
    automatically adding a newline and wrapping the message.

    :param msg: the message.
    :return: nothing
    """
    print(_debug_wrapper.fill("{}{}".format(DEBUG_PREFIX, msg)))


def _find_notebooks(dir, encoding):
    # type: (str, str) -> Sequence[str]
    """
    Find all source notebooks underneath a directory. Looks for Python,
    Scala, R and SQL files, by extension. Keeps only the ones with a valid
    Databricks notebook header.

    :param dir:      the directory to search
    :param encoding: the file encoding to use when opening the notebooks

    :return: the notebooks
    """
    notebooks = []
    for dirpath, _, filenames in os.walk(dir):
        for f in filenames:
            _, ext = os.path.splitext(f)
            path = os.path.join(dirpath, f)
            if not Notebook.is_source_notebook(path, encoding):
                _verbose('Skipping non-notebook "{}"'.format(path))
                continue

            notebooks.append(path)

    return tuple(notebooks)


def _parse_args():
    # type: () -> dict
    """
    Parse the command line parameters into a Config object. Aborts on error.

    :return: the parsed Config object
    """
    global _verbose

    args = docopt.docopt(USAGE, version=VERSION, options_first=True)

    source_dir = args['SRCDIR']
    if not os.path.exists(source_dir):
        _error('Source directory "{}" does not exist.'.format(source_dir))
        raise UsageError()
    elif not os.path.isdir(source_dir):
        _error('Source directory "{}" is not a directory.'.format(source_dir))
        raise UsageError()

    global _be_verbose
    _be_verbose = args['--verbose']

    return args


def _adjust_paths (notebooks, # type: Sequence[Notebook]
                   params     # type: Config
                   ):
    # type: (...) -> Sequence[str]
    """
    Adjusts the notebook paths, which means one of two things:

    - If "flatten" is enabled, all directory information is removed from
      the paths.
    - Otherwise, the source directory prefix is removed.

    :param notebooks: the notebooks
    :param params:    the parameters

    :return: a list of adjusted paths, in the same order as the notebooks
    """

    adj_paths = []
    if params.flatten:
        # Remove all the directory paths, leaving just the base file name.
        # If we get a conflict, abort.
        paths = set()
        clashes = set()
        for nb in notebooks:
            base = os.path.basename(nb.path)
            if base in paths:
                clashes.add(base)
            else:
                paths.add(base)
                adj_paths.append(base)
        if len(clashes) > 0:
            raise GendbcError(
                ('There are multiple notebooks with the following base file ' +
                 'names, so flattening is not possible: {}').format(
                    ', '.join([i for i in clashes])
                )
            )
    else:
        # Just strip the source directory from the paths.
        for nb in notebooks:
            if not nb.path.startswith(params.source_dir):
                raise Exception(
                    '''(BUG) Notebook "{}" doesn't start with "{}".'''.format(
                        nb.path, params.source_dir
                    )
                )
            if nb.path == params.source_dir:
                raise Exception(
                    '(BUG) Notebook IS source path?! "{}"'.format(nb.path)
                )
            new_path = nb.path[len(params.source_dir) + 1:]
            adj_paths.append(new_path)

    if params.dbc_folder:
        # Shove everything under this folder.
        adj_paths2 = []
        for p in adj_paths:
            adj_paths2.append(os.path.join(params.dbc_folder, p))

        adj_paths = adj_paths2

    return adj_paths


def _write_dbc(notebooks, # type: Sequence[Notebook]
               params     # type: Config
              ):
    # type: (...) -> None
    """
    Convert a list of notebooks to JSON and write them to the DBC file.

    :param notebooks: the parsed notebooks
    :param params:    the parameters

    :return: None
    """

    # The simplest solution is to write the JSON versions of the notebooks to
    # a temporary directory and use shutil.make_archive() to do the heavy
    # lifting.
    dbc_paths = _adjust_paths(notebooks, params)
    with TemporaryDirectory() as tempdir:
        for nb, zpath in zip(notebooks, dbc_paths):
            json = nb.to_json()
            # Wrinkle: Python JSON notebooks end in ".python", not ".py".
            file, ext = os.path.splitext(zpath)
            if ext == '.py':
                zpath = "{}.python".format(file)
            out_path = os.path.join(tempdir, zpath)
            dirname = os.path.dirname(zpath)
            if dirname and (dirname != '.'):
                dirpath = os.path.join(tempdir, dirname)
                if not os.path.exists(dirpath):
                    os.makedirs(dirpath)
            with codecs.open(out_path, mode='w', encoding=params.encoding) as w:
                w.write(json)
            _verbose('Wrote JSON notebook "{}"'.format(out_path))

        # Create the zip file.
        shutil.make_archive(params.dbc, 'zip', root_dir=tempdir)

        # make_archive() just created "something.dbc.zip". Rename it.
        os.rename(params.dbc + '.zip', params.dbc)

        # Finally, make_archive() did NOT create a comment in the zip file.
        # Let's add one, to indicate who created the DBC.
        with ZipFile(params.dbc, 'a') as z:
            z.comment = "gendbc (Python), version {}".format(VERSION)

# -----------------------------------------------------------------------------
# Public Functions
# -----------------------------------------------------------------------------

def gendbc(source_dir,  # type: str
           encoding,    # type: str
           dbc_path,    # type: str
           dbc_folder,  # type: str
           flatten,     # type: bool
           verbose,     # type: bool
           debug=False  # type: bool
          ):
    # type: (...) -> None
    """
    Generate a DBC from all the notebooks under a specific source directory.

    :param source_dir:  the directory to scan for source notebooks
    :param encoding:    the encoding to use when opening the notebooks
    :param dbc_path:    the path to the DBC file to create or overwrite
    :param dbc_folder:  top-level DBC folder to create, if any. None means
                        just use the partial paths.
    :param flatten:     If True, flatten all the files into one folder in the
                        zip file. If dbc_folder is specified, all files will
                        go in that folder. Otherwise, they'll be at the top
                        of the DBC.
    :param verbose:     Whether or not to emit verbose messages.
    :param debug:       Whether or not to emit debug messages.

    :return: nothing
    """
    params = Config(debug=debug,
                    verbose=verbose,
                    encoding=encoding,
                    dbc_folder=dbc_folder,
                    flatten=flatten,
                    show_stack=True,
                    source_dir=source_dir,
                    dbc=dbc_path)

    if params.dbc_folder and ('/' in params.dbc_folder):
        raise UsageError(
            ('The specified DBC top folder, "{}", must be a simple directory ' +
             'name, not a path.').format(params.dbc_folder)
        )

    notebook_paths = _find_notebooks(params.source_dir, params.encoding)

    if len(notebook_paths) == 0:
        _die('No source notebooks found under "{}".'.format(
            params.source_dir
        ))

    emit_debug = _debug if params.debug else None

    notebooks = [parse_source_notebook(i, params.encoding, emit_debug)
                 for i in notebook_paths]
    _write_dbc(notebooks, params)

# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------

def main():
    params = None
    show_stack = False
    try:
        args = _parse_args()
        show_stack = args['--stack']
        gendbc(source_dir=args['SRCDIR'],
               encoding=args['--encoding'],
               dbc_path=args['DBC'],
               dbc_folder=args['--folder'],
               flatten=args['--flatten'],
               verbose=args['--verbose'],
               debug=args['--debug'])
    except UsageError as e:
        if e.message:
            _error(e.message)
        # Already reported.
        sys.exit(1)
    except Exception as e:
        if show_stack:
            tb = traceback.format_exc()
            _printerr(tb)
        else:
            _error(str(e))
        sys.exit(1)

if __name__ == '__main__':
    main()
