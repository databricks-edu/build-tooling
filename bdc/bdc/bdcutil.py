'''
Utility functions and classes
'''

from abc import ABCMeta
import re
import os
from os import path
import contextlib
import markdown2
import shutil
import codecs

from future import standard_library
standard_library.install_aliases()

from string import Template
from textwrap import TextWrapper

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# This is the HTML template into which converted Markdown will be inserted.
# There are several substitution parameters:
#
# $title - the document's title
# $css   - where the stylesheet is inserted
# $body  - where the converted Markdown HTML goes
DEFAULT_HTML_TEMPLATE = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>$title</title>
    <style type="text/css">
$css
    </style>
  </head>
  <body>
$body
  </body>
</html>
"""

DEFAULT_CSS = """body {
  font-family: sans-serif;
  margin-left: 0.75in;
  margin-right: 0.5in;
}
tt, pre, code {
  font-family: Consolas, Menlo, monospace;
}
table thead tr th {
  border-bottom: 1px solid #ccc;
}
table tbody tr:nth-child(even) {
  background: #ccc;
}
table tbody tr:nth-child(odd) {
  background: #fff;
}
tr td {
  padding: 5px;
}
h1, h2, h3, h4, h5, h6 {
  font-family: Newslab, sans-serif;
  margin-left: -0.25in;
}
h3 {
  font-style: italic;
}
h4 {
  text-decoration: underline;
}
"""

COLUMNS = int(os.getenv('COLUMNS', '79'))
WARNING_PREFIX = "*** WARNING: "

# ---------------------------------------------------------------------------
# Module globals
# ---------------------------------------------------------------------------

_verbose = False
_verbose_prefix = ''

# Text wrappers
_warning_wrapper = TextWrapper(width=COLUMNS,
                               subsequent_indent=' ' * len(WARNING_PREFIX))

_verbose_wrapper = TextWrapper(width=COLUMNS)

_error_wrapper = TextWrapper(width=COLUMNS)

_info_wrapper = TextWrapper(width=COLUMNS, subsequent_indent=' ' * 4)

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def set_verbosity(verbose, verbose_prefix):
    '''
    Set or clear verbose messages.

    :param verbose:        True or False to enable or disable verbosity
    :param verbose_prefix  string to use as a prefix for verbose messages, or
                           None (or empty string) for no prefix
    '''
    global _verbose
    global _verbose_prefix
    global _verbose_wrapper

    _verbose = verbose
    if verbose_prefix:
        _verbose_prefix = verbose_prefix
        _verbose_wrapper = TextWrapper(
            width=COLUMNS,
            subsequent_indent=' ' * len(verbose_prefix)
        )


def verbosity_is_enabled():
    '''
    Determine whether verbosity is on or off.

    :return:  True or False
    '''
    return _verbose


def verbose(msg):
    '''
    Conditionally emit a verbose message. See also set_verbosity().

    :param msg: the message

    :return:
    '''
    if _verbose:
        print(_verbose_wrapper.fill("{0}{1}".format(_verbose_prefix, msg)))


def warning(msg):
    '''
    Emit a warning message.

    :param msg: The message
    '''
    print(_warning_wrapper.fill('{0}{1}'.format(WARNING_PREFIX, msg)))


def info(msg):
    '''
    Emit an informational message.

    :param msg: The message
    '''
    print(_info_wrapper.fill(msg))


def emit_error(msg):
    '''
    Emit an error message.

    :param msg: The message
    '''
    print('***')
    print(_error_wrapper.fill(msg))
    print('***')


def parse_version_string(version):
    '''
    Parse a semantic version string (e.g., 1.10.30) or a partial
    <major>.<minor> semver string (e.g., 1.10) into a tuple of
    (major, minor, patch) or (major, minor) integers. Raises ValueError for
    a malformed version string. The patch level (third number) is ignored

    :param version:  the string to parse

    :return:  A `(major, minor)` tuple of ints.
    '''
    nums = version.split('.')
    if len(nums) not in (2, 3):
        raise ValueError('"{0}" is a malformed version string'.format(version))
    try:
        return tuple([int(i) for i in nums])
    except ValueError as e:
        raise ValueError('"{0}" is a malformed version string: {1}'.format(
            version, e.message
        ))


def merge_dicts(dict1, dict2):
    '''
    Merge two dictionaries, producing a third one

    :param dict1:  the first dictionary
    :param dict2:  the second dictionary

    :return: The merged dictionary. Keys in dict2 overwrite duplicate keys in
             dict1
    '''
    res = dict1.copy()
    res.update(dict2)
    return res


def bool_field(d, key, default=False):
    '''
    Get a boolean value from a dictionary, parsing it if it's a string.

    :param d:       the dictionary
    :param key:     the key
    :param default: the default, if not found

    :return: the value

    :raise ValueError on error
    '''
    return bool_value(d.get(key, default))


def bool_value(s):
    '''
    Convert a string to a boolean value. Raises ValueError if the string
    isn't boolean.

    :param s: the string

    :return: the boolean
    '''
    if isinstance(s, bool):
        return s

    sl = s.lower()
    if sl in ('t', 'true', '1', 'yes'):
        return True
    elif sl in ('f', 'false', '0', 'no'):
        return False
    else:
        raise ValueError('Bad boolean value: "{0}"'.format(s))


def variable_ref_patterns(variable_name):
    '''
    Convert a variable name into a series of regular expressions that will will
    match a reference to the variable. (Regular expression alternation syntax
    is too complicated and error-prone for this purpose.)

    Each regular expression matches one form of the variable syntax, and each
    regular expression has three groups:

    Group 1 - The portion of the string that precedes the variable reference
    Group 2 - The variable reference
    Group 3 - The portion of the string those follows the variable reference

    For convenience, use the result with matches_variable_ref().

    :param variable_name: the variable name

    :return: The compiled regular expressions, as an iterable tuple
    '''
    return (
        re.compile(r'^(.*)(\$\{' + variable_name + r'\})(.*)$'),
        re.compile(r'^(.*)(\$' + variable_name + r')([^a-zA-Z_]+.*)$'),
        re.compile(r'^(.*)(\$' + variable_name + r')()$') # empty group 3
    )


def matches_variable_ref(patterns, string):
    '''
    Matches the string against the pattern, returning a 3-tuple on match and
    None on no match.

    :param patterns: A series of patterns returned from variable_ref_patterns().
    :param string:   The string against which to match.

    :return: None if no match. If match, a 3-tuple containing three elements:
             the portion of the string preceding the variable reference,
             the variable reference, and the portion of the string following
             the variable reference
    '''
    for p in patterns:
        m = p.match(string)
        if m:
            return m.groups()
    else:
        return None


@contextlib.contextmanager
def working_directory(path):
    """
    Simple context manager that runs the code under "with" in a specified
    directory, returning to the original directory when the "with" exits.
    """
    prev = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(prev)


def find_in_path(command):
    '''
    Find a command in the path, or bail.

    :param command:  the command to find
    :return: the location. Throws an exception otherwise.
    '''
    path = [p for p in os.getenv('PATH', '').split(os.pathsep) if len(p) > 0]
    for d in path:
        p = os.path.join(d, command)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    else:
        raise Exception("""Can't find "{0}" in PATH.""".format(command))


def ensure_parent_dir_exists(path):
    '''
    Ensures that the parent directory of a path exists.

    :param path: The path whose parent directory must exist.
    '''
    mkdirp(os.path.dirname(path))


def move(src, dest, ensure_final_newline=False, encoding='UTF-8'):
    """
    Copy a source file to a destination file, honoring the --verbose
    command line option and creating any intermediate destination
    directories.

    :param src:                  src file
    :param dest:                 destination file
    :param ensure_final_newline  if True, ensure that the target file has
                                 a final newline. Otherwise, just copy the
                                 file exactly as is, byte for byte.
    :param encoding              Only used if ensure_file_newline is True.
                                 Defaults to 'UTF-8'.
    :return: None
    """
    _do_copy(
        src, dest, ensure_final_newline=ensure_final_newline, encoding=encoding
    )
    os.unlink(src)


def joinpath(*pieces):
    '''
    Similar to os.path.join(), this function joins the path components, but
    also normalizes the path.

    :param pieces: the path pieces

    :return: the joined an normalized path
    '''
    return os.path.normpath(os.path.join(*pieces))


def rm_rf(path):
    '''
    Equivalent of "rm -rf dir", this function is similar to
    shutil.rmtree(dir), except that it doesn't abort if the directory does
    not exist. It also silently handles regular files. This function throws
    an OSError if the passed file is neither a regular file nor a directory.

    :param path: The directory or file to (recursively) remove, if it
                        exists.
    '''
    if os.path.exists(path):
        if os.path.isfile(path):
            os.unlink(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            raise OSError(
                '"{0}" is neither a file nor a directory'.format(path)
            )


def mkdirp(dir):
    '''
    Equivalent of "mkdir -p".

    :param dir: The directory to be created, along with any intervening
                parent directories that don't exist.
    '''
    if not path.exists(dir):
        os.makedirs(dir)


def copy(src, dest, ensure_final_newline=False, encoding='UTF-8'):
    """
    Copy a source file to a destination file, honoring the --verbose
    command line option and creating any intermediate destination
    directories.

    :param src:                  src file
    :param dest:                 destination file
    :param ensure_final_newline  if True, ensure that the target file has
                                 a final newline. Otherwise, just copy the
                                 file exactly as is, byte for byte.
    :param encoding              Only used if ensure_file_newline is True.
                                 Defaults to 'UTF-8'.
    :return: None
    """
    _do_copy(
        src, dest, ensure_final_newline=ensure_final_newline, encoding=encoding
    )


def markdown_to_html(markdown, html_out, html_template=None, stylesheet=None):
    """
    Convert a Markdown file to HTML, writing it to the specified HTML file.
    If the stylesheet is specified, it is inserted.

    :param markdown:      The path to the Markdown file
    :param html_out       The path to the desired HTML output file
    :param html_template  A template for the HTML, or None to use the
                          default.
    :param stylesheet     A string containing a stylesheet to inline, or None
                          to use the default
    """
    with codecs.open(markdown, mode='r', encoding='UTF-8') as input:
        text = input.read()
        body = markdown2.markdown(text, extras=['fenced-code-blocks',
                                                'tables'])
        if stylesheet is None:
            stylesheet = DEFAULT_CSS

        if html_template is None:
            html_template = DEFAULT_HTML_TEMPLATE

        template = Template(html_template)

        with codecs.open(html_out, mode='w', encoding='UTF-8') as output:
            output.write(
                template.substitute(
                    body=body,
                    title=path.basename(markdown),
                    css=stylesheet
                )
            )


def dict_get_and_del(d, key, default=None):
    '''
    Get the value of a key from a dictionary, and remove the key.

    :param d:        the dictionary
    :param key:      the key
    :param default:  the default value, if the key isn't present

    :return: The value, with d possibly modified
    '''
    if key in d:
        res = d[key]
        del d[key]
        return res

    return default

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class DefaultStrMixin:
    '''
    Provides default implementations of __str__() and __repr__(). These
    implementations assume that all arguments passed to the constructor are
    captured in same-named fields in "self".
    '''
    __metaclass__ = ABCMeta

    def __str__(self):
        indent = ' ' * (len(self.__class__.__name__) + 1)
        fields = []
        for key in sorted(self.__dict__.keys()):
            value = self.__dict__[key]
            v = '"{0}"'.format(value) if isinstance(value, str) else value
            fields.append('{0}={1}'.format(key, v))

        delim = ',\n{0}'.format(indent)
        return '{0}({1})'.format(self.__class__.__name__, delim.join(fields))

    def __repr__(self):
        return self.__str__()

# ---------------------------------------------------------------------------
# Module-private functions
# ---------------------------------------------------------------------------

def _do_copy(src, dest, ensure_final_newline=False, encoding='UTF-8'):
    # Workhorse function that actually copies a file. Used by move() and
    # copy().
    if not path.exists(src):
        raise IOError('"{0}" does not exist.'.format(src))
    src = path.abspath(src)
    dest = path.abspath(dest)
    ensure_parent_dir_exists(dest)

    if not ensure_final_newline:
        shutil.copy2(src, dest)
    else:
        with codecs.open(src, mode='r', encoding=encoding) as input:
            with codecs.open(dest, mode='w', encoding=encoding) as output:
                last_line_had_nl = False
                for line in input:
                    output.write(line)
                    last_line_had_nl = line[-1] == '\n'
                if not last_line_had_nl:
                    output.write('\n')
        shutil.copystat(src, dest)
