'''
Utility functions and classes

Run this module as a main program, or run it through `python -m doctest`,
to exercise embedded tests.
'''

from abc import ABCMeta
import re
import os
from os import path
import contextlib
import markdown2
import shutil
import codecs
from collections import namedtuple
import parsimonious
from parsimonious.grammar import Grammar
from parsimonious import grammar, expressions
from parsimonious.exceptions import ParseError, VisitationError
from textwrap import TextWrapper

from future import standard_library
standard_library.install_aliases()

from string import Template

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

def all_pred(func, iterable):
    '''
    Similar to the built-in `all()` function, this function ensures that
    `func()` returns `True` for every element of the supplied iterable.
    It short-circuits on the first failure.

    :param func:     function or lambda to call with each element
    :param iterable: the iterable

    :return: `True` if all elements pass, `False` otherwise
    '''
    for i in iterable:
        if not func(i):
            return False

    return True


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

    >>> parse_version_string("2.0.3")
    (2, 0)
    >>> parse_version_string("2.3")
    (2, 3)
    >>> parse_version_string("2")
    Traceback (most recent call last):
    ...
    ValueError: ...
    >>> parse_version_string("2.4.3.1")
    Traceback (most recent call last):
    ...
    ValueError: "2.4.3.1" is a malformed version string
    >>> parse_version_string("abc")
    Traceback (most recent call last):
    ...
    ValueError: "abc" is a malformed version string
    >>> parse_version_string("a.b.c")
    Traceback (most recent call last):
    ...
    ValueError: "a.b.c" is a malformed version string...
    '''
    nums = version.split('.')
    if len(nums) not in (2, 3):
        raise ValueError('"{0}" is a malformed version string'.format(version))
    try:
        return tuple([int(i) for i in nums])[0:2]
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

    >>> x = {'a': 10, 'b': 30, 'c': 'hello'}
    >>> y = {'d': 40, 'b': 'Bee', 'x': 'Ecks'}
    >>> sorted(list(merge_dicts(x, y).items()))
    [('a', 10), ('b', 'Bee'), ('c', 'hello'), ('d', 40), ('x', 'Ecks')]
    >>> sorted(list(merge_dicts(y, x).items()))
    [('a', 10), ('b', 30), ('c', 'hello'), ('d', 40), ('x', 'Ecks')]
    >>> sorted(list(x.items())) # should not be modified
    [('a', 10), ('b', 30), ('c', 'hello')]
    >>> sorted(list(y.items())) # should not be modified
    [('b', 'Bee'), ('d', 40), ('x', 'Ecks')]
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

    >>> d = {'a': 0, 'b': 10, 'c': 'false', 'd': 'TRUE', 'e': 'No',\
             'f': 'yeS', 'g': True, 'h': 'hello'}
    >>> bool_field(d, 'a')
    False
    >>> bool_field(d, 'b')
    True
    >>> bool_field(d, 'c')
    False
    >>> bool_field(d, 'd')
    True
    >>> bool_field(d, 'e')
    False
    >>> bool_field(d, 'f')
    True
    >>> bool_field(d, 'g')
    True
    >>> bool_field(d, 'h')
    Traceback (most recent call last):
    ...
    ValueError: Bad boolean value: "hello"
    '''
    return bool_value(d.get(key, default))


def bool_value(s):
    '''
    Convert a string to a boolean value. Raises ValueError if the string
    isn't boolean.

    :param s: the string

    :return: the boolean

    >>> bool_value('0')
    False
    >>> bool_value(100)
    True
    >>> bool_value(0)
    False
    >>> bool_value('true')
    True
    >>> bool_value('TRUE')
    True
    >>> bool_value('yes')
    True
    >>> bool_value('YeS')
    True
    >>> bool_value('no')
    False
    >>> bool_value('booyah')
    Traceback (most recent call last):
    ...
    ValueError: Bad boolean value: "booyah"
    '''
    if isinstance(s, bool):
        return s

    if isinstance(s, int):
        return False if s == 0 else True

    sl = s.lower()
    if sl in ('t', 'true', '1', 'yes'):
        return True
    elif sl in ('f', 'false', '0', 'no'):
        return False
    else:
        raise ValueError('Bad boolean value: "{0}"'.format(s))


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

    >>> os.path.basename(find_in_path('python'))
    'python'
    >>> find_in_path('asdhf-asdiuq')
    Traceback (most recent call last):
    ...
    Exception: Can't find "asdhf-asdiuq" in PATH.
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

    >>> joinpath('a///', 'b/') if os.name == 'posix' else 'a/b'
    'a/b'
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

    >>> d = {'a': 10, 'b': 20, 'c': 30}
    >>> dict_get_and_del(d, 'a')
    10
    >>> sorted(list(d.items()))
    [('b', 20), ('c', 30)]
    >>> dict_get_and_del(d, 'x', -1)
    -1
    >>> sorted(list(d.items()))
    [('b', 20), ('c', 30)]
    '''
    if key in d:
        res = d[key]
        del d[key]
        return res

    return default


def variable_ref_patterns(variable_name):
    '''
    Convert a variable name into a series of regular expressions that will will
    match a reference to the variable. (Regular expression alternation syntax
    is too complicated and error-prone for this purpose.)

    Each regular expression matches one form of the variable syntax, and each
    regular expression has three groups:

    ---------------------------------------------------------------------------
    NOTE: This function is coupled to the `VariableSubstituter` class's
    grammar.
    ---------------------------------------------------------------------------

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
        re.compile(r'^(.*)(\$' + variable_name + r')()$'), # empty group 3
        # This next bit of ugliness matches the ternary IF syntax
        re.compile(r'^(.*)(\${' + variable_name + r'\s*[=!]=\s*"[^}?:]*"\s*\?\s*"[^}?:]*"\s*:\s*"[^}?:]*"})(.*)$')
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

    >>> pats = variable_ref_patterns
    >>> matches_variable_ref(pats('foo'), '$foo')
    ('', '$foo', '')
    >>> matches_variable_ref(pats('hello'), 'This is ${hello} a')
    ('This is ', '${hello}', ' a')
    >>> matches_variable_ref(pats('foobar'), "abc $bar cdef.")
    >>> matches_variable_ref(pats('nb'), '$foo bar ${nb == "abc" ? "one" : "two"}')
    ('$foo bar ', '${nb == "abc" ? "one" : "two"}', '')
    >>> matches_variable_ref(pats('nb'), '$foo bar ${nb=="abc"?"one":"two"}')
    ('$foo bar ', '${nb=="abc"?"one":"two"}', '')
    '''

    for p in patterns:
        m = p.match(string)
        if m:
            return m.groups()
    else:
        return None


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class DefaultStrMixin:
    '''
    Provides default implementations of __str__() and __repr__(). These
    implementations assume that all arguments passed to the constructor are
    captured in same-named fields in `self`.
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
# Variable Substitution Code
# ---------------------------------------------------------------------------

# These constants define a Parsing Expression Grammar (PEG) for template
# substitution, used by the VariableSubstituter class.
#
# DO NOT CHANGE THESE VARIABLES UNLESS YOU UNDERSTAND HOW PEG WORKS!
#
# The grammar is parsed with Parsimonious. See
# https://github.com/erikrose/parsimonious
#
# See https://en.wikipedia.org/wiki/Parsing_expression_grammar for an
# introduction to PEG.
#
# NOTE: Even simple terminal constants (like '"') have token names. The
# visitor relies on this behavior. Changes to the grammar will affect
# the visitor, so be careful.

_VAR_SUBST_EQ_OP = '=='
_VAR_SUBST_NE_OP = '!='

_VAR_SUBST_OPS = {   # the supported ternary expression operators
    _VAR_SUBST_EQ_OP, _VAR_SUBST_NE_OP
}

_VAR_SUBST_EDIT_DELIM1          = '/'
_VAR_SUBST_EDIT_DELIM2          = '|'
_VAR_SUBST_EDIT_GROUPREF_PREFIX = '$'

def _replace_tokens(s, tokens):
    s2 = s
    for token, replacement in tokens.items():
        s2 = s2.replace(token, replacement)
    return s2

# The grammar itself. Some values are substituted, so they can be shared
# with the code (the PEG alternation syntax).
_VAR_SUBST_OPS_RULE = ' / '.join(['"{}"'.format(op) for op in _VAR_SUBST_OPS])
_VAR_SUBST_GRAMMAR = _replace_tokens(r"""
# A line consists of zero or more terms. 
line                  = term*

# A term consists of an edit or a ternary expression or a variable substitution
# or text. Order is important here, since first match wins.
term                  = edit / ternary / var / text

# Two forms of variable references are permitted: $var and ${var}
var                   = var1 / var2
var1                  = '$' identifier
var2                  = "${" identifier '}'

backslash             = '\\'
char                  = ~"."

# Only double quotes are permitted in quoted strings.
quote                 = '"'

# NOTE: "!" is a negative lookahead assertion: It asserts that the token isn't
# present, but doesn't consume anything. Thus, "!quote" asserts that the first
# character isn't a quote, but doesn't consume it, so it'll get picked up
# by "char".  

optional_text         = (!quote char)*
required_text         = (!quote char)+

# Ternary IF. Format:
# 
#    ${var == "SOMESTRING" ? "TRUESUB" : "FALSESUB"}
#    ${var != "SOMESTRING" ? "TRUESUB" : "FALSESUB"}

ternary               = "${"
                        identifier OPT_WS
                        compare_op OPT_WS
                        ternary_compare_term OPT_WS
                        ternary_op OPT_WS
                        ternary_true_side OPT_WS
                        ternary_else OPT_WS
                        ternary_false_side
                        '}'
ternary_true_side     = quote optional_text quote
ternary_false_side    = quote optional_text quote
ternary_compare_term  = quote optional_text quote
ternary_op            = '?'
ternary_else          = ':'

# @OPS@ is substituted from Python vars, allowing sharing with the code. 
compare_op            = @OPS@

# Inline edit during variable substitution. Format:
#
#    ${var/regex/repl/flags}
#    ${var|regex|repl|flags}
#
# In the regex and the replacement string, delimiters ("|" and "/") can be
# escaped with a preceding "\". It's usually more readable to use the
# alternate delimiter, though.
#
# In the replacement string, regex capture groups can be referenced with a "$"
# syntax (e.g., "$1"). A literal "$" can be espressed as "\$".
#
# Flags (optional):
#   i - case-independent matching
#   g - replace all matches, not just the first
#
# Examples:
#
#    ${foo/^[a-z]/X/g}                    replace all lower case letters with X
#    ${file|(\d+)(-.*)$|$1a-$2|}   Insert an "a" after any leading digits,
#                                  and before the "-". e.g.: "01-Foobar"
#                                  becomes "01a-Foobar".

edit                  = edit1 / edit2
edit1                 = "${"
                        identifier
                        edit_delim1
                        pattern1
                        edit_delim1
                        replacement1
                        edit_delim1
                        flags
                        '}'
edit2                 = "${"
                        identifier
                        edit_delim2
                        pattern2
                        edit_delim2
                        replacement2
                        edit_delim2
                        flags
                        '}'
flags                 = (~"[a-z]"i)*

edit_delim1           = @EDIT_DELIM_1@
non_edit_delim1       = (backslash edit_delim1) /
                        (backslash groupref_prefix) /
                        (!edit_delim1 char)
pattern1              = non_edit_delim1+
replacement1          = (groupref / non_edit_delim1)*

edit_delim2           = @EDIT_DELIM_2@
non_edit_delim2       = (backslash edit_delim2) /
                        (backslash groupref_prefix) /
                        (!edit_delim2 char)
pattern2              = non_edit_delim2+
replacement2          = (groupref / non_edit_delim2)*

groupref_prefix       = @EDIT_GROUPREF_PREFIX@
groupref              = (!backslash groupref_prefix digit)

digit                 = ~"\d"
identifier            = ~"[A-Z0-9_]+"i
nonvar1               = ~"[^$]+"
nonvar2               = ~"[^$]*\$\$[^$]*"
nonvar                = nonvar1 / nonvar2
text                  = nonvar*
OPT_WS                = ~"\s*"
""", {
    "@OPS@":                  _VAR_SUBST_OPS_RULE,
    "@EDIT_DELIM_1@":         "'" + _VAR_SUBST_EDIT_DELIM1 + "'",
    "@EDIT_DELIM_2@":         "'" + _VAR_SUBST_EDIT_DELIM2 + "'",
    "@EDIT_GROUPREF_PREFIX@": "'" + _VAR_SUBST_EDIT_GROUPREF_PREFIX + "'",
})

#print(_VAR_SUBST_GRAMMAR);import sys;sys.exit(1)

class VariableSubstituterParseError(Exception):
    pass

class VariableSubstituter(object):
    '''
    Conceptually similar to the Python string Template class, this class
    supports `$var` and `${var}` substitutions. However, it *also* supports
    a C-like ternary IF: `${var=="somestring"?"truestring":"falsestring"}`.
    White space is ok: `${var == "somestring" ? "truestring" : "falsestring"}`.

    Similar to `string.Template`, this class supports two forms of substitution:

    - a `substitute()` method, which bails if a referenced variable isn't
      defined
    - a `safe_substitute()` method, which substitutes an empty string for
      undefined variables. (This behavior differs from `string.Template`)

    Variable identifiers can consist of alphanumeric and underscore characters.

    >>> template = '$foo $$ ${bar} ${a == "hello" ? "woof" : "x"}'
    >>> v = VariableSubstituter(template)
    >>> v.template == template
    True
    >>> v.substitute({'foo': 'FOO', 'bar': 'BAR', 'a': 'hello'})
    'FOO $$ BAR woof'
    >>> v.substitute({'foo': 'FOO', 'a': 'hello'})
    Traceback (most recent call last):
    ...
    KeyError: 'bar'
    >>> v.safe_substitute({'foo': 'FOO', 'a': 'hello'})
    'FOO $$  woof'
    >>> v = VariableSubstituter('${foo $bar')
    Traceback (most recent call last):
    ...
    VariableSubstituterParseError: Failed to parse ...
    >>> v = VariableSubstituter('${foo} $bar')
    >>> v.substitute({'foo': 10, 'bar': 20})
    '10 20'
    >>> v.substitute({'foo': '', 'bar': ''})
    ' '
    >>> v = VariableSubstituter('$foo bar ${baz/[a-z]/x/gi}')
    >>> v.substitute({'foo': 'Jimmy', 'baz': 'John'})
    'Jimmy bar xxxx'
    >>> v = VariableSubstituter('$foo bar ${baz/[a-z]\/[a-z]/x\/y/i}')
    >>> v.substitute({'foo': 'Jimmy', 'baz': 'b/d/c/e'})
    'Jimmy bar x/y/c/e'
    >>> v = VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y|i}')
    >>> v.substitute({'foo': 'Jimmy', 'baz': 'b/d/c/e'})
    'Jimmy bar x/y/c/e'
    >>> v = VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y|igx}')
    Traceback (most recent call last):
    ...
    VariableSubstituterParseError: Failed to parse ...
    >>> v = VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y') # missing last |
    Traceback (most recent call last):
    ...
    VariableSubstituterParseError: Failed to parse ...
    >>> v = VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y|') # no }
    Traceback (most recent call last):
    ...
    VariableSubstituterParseError: Failed to parse ...
    >>> v = VariableSubstituter('$foo bar ${baz|[a-z]/[a-z]|x/y|}') # no flags
    >>> v.substitute({'foo': 'Jimmy', 'baz': 'B/d/c/e'})
    'Jimmy bar B/x/y/e'
    >>> v = VariableSubstituter('${foo|[a-z]+/\d+|FOOBAR|g}')
    >>> v.substitute({'foo': 'abcdef/123/999-/vbn/789'})
    'FOOBAR/999-/FOOBAR'
    >>> v = VariableSubstituter('${file|^(\d+)|$1s|g}')
    >>> v.substitute({'file': '01-Why-Spark.py'})
    '01s-Why-Spark.py'
    >>> v = VariableSubstituter('${file|^(\d+)(-.*)$|$1s$2|g}')
    >>> v.substitute({'file': '01-Why-Spark.py'})
    '01s-Why-Spark.py'
    >>> v = VariableSubstituter('${file|^(\d+)(-.*)$|$1s$2$3|g}')
    Traceback (most recent call last):
    ...
    VariableSubstituterParseError: Failed to parse ...non-existent group...
    >>> v = VariableSubstituter('${file|^(\d+)(-.*)$|$1s$2\$4\$2|}')
    >>> v.substitute({'file': '01-Why-Spark.py'})
    '01s-Why-Spark.py$4$2'
    >>> v = VariableSubstituter('${file|abcdef|ZYXWVU|}')
    >>> v.substitute({'file': 'abcdef abcdef'})
    'ZYXWVU abcdef'
    >>> v.substitute({'file': 'foobar'})
    'foobar'
    >>> v = VariableSubstituter('${file|^[.*$|x|}')
    Traceback (most recent call last):
    ...
    VariableSubstituterParseError: Failed to parse ...Bad regular expression ...
    >>> v = VariableSubstituter('${file/abc//}')
    >>> v.substitute({'file': 'abc123abc'})
    '123abc'
    >>> v = VariableSubstituter('${file/abc//g}')
    >>> v.substitute({'file': 'abc123abc'})
    '123'
    >>> v = VariableSubstituter('${file/\d//g}')
    >>> v.substitute({'file': 'abc123abc2'})
    'abcabc'
    >>> v = VariableSubstituter('${file/\d//}')
    >>> v.substitute({'file': 'abc123abc2'})
    'abc23abc2'
    >>> v = VariableSubstituter(r'${file/\.py$//}')
    >>> v.substitute({'file': 'Foobar.py'})
    'Foobar'
    '''

    def __init__(self, template):
        '''
        Create a new variable substituter.

        :param template: The template containing variables to substitute.
        '''
        self._template = template
        try:
            self._grammar = Grammar(_VAR_SUBST_GRAMMAR)
            parsimonious_ast = self._grammar.parse(template)
            visitor = _VarSubstASTVisitor()
            self._ast = self._flatten(visitor.visit(parsimonious_ast))

        except ParseError as e:
            if e.message:
                raise VariableSubstituterParseError(
                    'Failed to parse "{0}: {1}'.format(
                        self.template, e.message
                    )
                )
            else:
                raise VariableSubstituterParseError(
                    'Failed to parse "{0}".'.format(self.template)
            )
        except VisitationError as e:
            # This is ugly and would not be necessary if VisitationError
            # contained the original thrown exception. The visitor in this
            # package can throw validation exceptions, which the caller
            # should see as is, without all the Parsimonious parse tree data
            # (which isn't helpful to the caller, since we're hiding it in
            # here).
            #
            # Since we can't actually test the nested exception, we have to
            # check the text of the message.
            pat = re.compile(r'^.*VariableSubstituterParseError: (.*)\s*Parse tree:')
            msg = e.message.replace('\n', ' ')
            m = pat.search(msg)
            if m:
                raise VariableSubstituterParseError(
                   'Failed to parse "{0}: {1}'.format(self.template, m.group(1))
                )
            else:
                raise VariableSubstituterParseError(
                    'Failed to parse "{0}"'.format(self.template)
                )

    @property
    def template(self):
        '''
        Get the template.

        :return:  the template string
        '''
        return self._template

    def substitute(self, variables):
        '''
        Substitute all variable references and ternary IFs in the template,
        using the supplied variables. This method will throw an `KeyError` if
        it encounters any variable reference that isn't in the supplied
        dictionary.

        :param variables: A dictionary of variable name to value mappings

        :return: The substituted string
        '''
        def get_var(varname):
            return str(variables[varname])

        return self._subst(get_var)

    def safe_substitute(self, variables):
        '''
        Substitute all variable references and ternary IFs in the template,
        using the supplied variables. This method will substitute an empty
        string for any variable reference that isn't in the supplied dictionary.
        Note that this behavior differs from `string.Template`, which leaves
        the variable reference alone. Thus, given this template::

            ${foo}: ${bar}${baz}

        and these variables::

            {'foo': "a", 'bar': "", 'baz': 10}

        `string.Template.safe_substitute()` returns `a: $bar10`, whereas this
        method returns `a: 10`

        :param variables: A dictionary of variable name to value mappings

        :return: The substituted string
        '''
        def get_var(varname):
            return str(variables.get(varname, ''))

        return self._subst(get_var)

    def _flatten(self, nested_list):
        res = []
        for i in nested_list:
            if type(i) is list:
                res.extend(self._flatten(i))
            else:
                res.append(i)
        return res

    def _subst(self, get_var):
        result = ""
        for token in self._ast:
            if type(token) is _Var:
                result += get_var(token.name)
            elif type(token) == _Text:
                result += token.text
            elif type(token) == _Ternary:
                result += token.evaluate(get_var(token.variable))
            elif type(token) == _Edit:
                result += token.evaluate(get_var(token.variable))
            else:
                raise KeyError('(BUG) Unknown token: {0}'.format(token))

        return result


class _Var(DefaultStrMixin):
    '''
    Captures a variable name in the modified (i.e., non-Parsimonious) AST.
    '''
    def __init__(self, name):
        '''
        Create a new variable reference.

        :param name: the variable name
        '''
        self.name = name


class _Text(DefaultStrMixin):
    '''
    Captures arbitrary text in the modified (i.e., non-Parsimonious) AST.
    '''
    def __init__(self, text):
        '''
        Create a new text container.

        :param text: the contents of the text
        '''
        self.text = text


class _Ternary(DefaultStrMixin):
    '''
    Captures the pieces of a ternary IF.
    '''
    def __init__(self, variable, op, to_compare, if_true, if_false):
        '''
        Create a new _Ternary object.

        :param variable:    the variable to substitute and test
        :param op:          the operation (one of OPS)
        :param to_compare:  the string against which to compare the variable
        :param if_true:     the string to substitute if the comparison is true
        :param if_false:    the string to substitute if the comnparison is false
        '''
        self.variable   = variable
        self.op         = op
        self.to_compare = to_compare
        self.if_true    = if_true
        self.if_false   = if_false

    def evaluate(self, variable_value):
        '''
        Convenience method: Takes the value for the variable (which the caller
        must provide) and performs the appropriate test, returning the
        `if_true` value if the comparison succeeds and the `if_false` value
        otherwise.

        :param variable_value:

        :return: the substitution
        '''
        if self.op == _VAR_SUBST_EQ_OP:
            test = variable_value == self.to_compare
        else:
            test = variable_value != self.to_compare

        if test is True:
            return self.if_true
        else:
            return self.if_false

class _Edit(DefaultStrMixin):
    '''
    Stores the pieces of an inline variable value edit.
    '''
    def __init__(self, variable, pattern, repl, flags, replace_all=False):
        self.variable = variable
        self.pattern = pattern
        self.repl = repl
        self.flags = flags
        self.replace_all = replace_all

    def evaluate(self, variable_value):
        value = str(variable_value)
        count = 0 if self.replace_all else 1
        return self.pattern.sub(self.repl, value, count=count)

class _VarSubstASTVisitor(grammar.NodeVisitor):
    GROUPREF_RE  = re.compile(r'^groupref$')
    NON_DELIM_RE = re.compile(r'^non_edit_delim\d$')

    '''
    This visitor translates the parsed Parsimonious AST into something more
    useful to the template substituter.
    '''
    def generic_visit(self, node, visited_children):
        '''
        Called to visit any other node. This method must be here, or the
        visit logic will bail. This code is adapted from code within
        Parsimonious. Basically, if the node has children, we replace the
        node with its children. Otherwise, we return the node.

        :param node:              the node
        :param visited_children:  its children

        :return: the node or its children
        '''
        return visited_children or node

    def visit_var1(self, node, children):
        '''
        Called to visit "var1" nodes

        :param node:     the node
        :param children: any related children

        :return: A `_Var` object
        '''
        return _Var(node.text[1:])

    def visit_var2(self, node, children):
        '''
        Called to visit "var2" nodes

        :param node:     the node
        :param children: any related children

        :return: A `_Var` object
        '''
        return _Var(node.text[2:-1])

    def visit_text(self, node, children):
        '''
        Called to visit text nodes.

        :param node:     the node
        :param children: any related children

        :return: a `_Text` object
        '''
        return _Text(node.text)

    def visit_ternary(self, node, children):
        '''
        Called to visit a ternary IF reference.

        :param node:     The node
        :param children: Its children

        :return: A `_Ternary` object.
        '''
        # This is somewhat complicated, as it needs to handle multiple tokens.
        # Looping over the children is safer than direct indexing, and it's
        # less likely to break when the grammar is slightly modified.
        # Here, we simply loop through the node itself, which will give us
        # children the next level down (i.e., directly under the "ternary"
        # node). We match against those nodes, and find *their* children as
        # necessary.
        #
        # THIS CODE IS COUPLED TIGHTLY TO THE GRAMMAR.
        var = None
        to_compare = None
        if_true = None
        if_false = None
        op = None
        for child in node:
            try:
                expr = child.expr
            except AttributeError:
                continue

            if expr.name == 'identifier':
                # The only identifier token here is the variable.
                var = child.text

            elif child.text in _VAR_SUBST_OPS:
                # Capture the comparison operation.
                op = child.text

            elif expr.name == 'ternary_compare_term':
                to_compare = self._find_child(child, 'optional_text').text

            elif expr.name == 'ternary_true_side':
                if_true = self._find_child(child, 'optional_text').text

            elif expr.name == 'ternary_false_side':
                if_false = self._find_child(child, 'optional_text').text

        if not all_pred(lambda i: i is not None,
                        [var, op, to_compare, if_true, if_false]):
            raise VariableSubstituterParseError(
                ('(BUG) Unable to find all expected pieces of parsed ternary ' +
                 'expression: "{}". var={}, op={}, to_compare={}, if_true={} ' +
                 'if_false={}').format(
                    node.text, var, op, to_compare, if_true, if_false
                )
            )
        return _Ternary(variable=var, op=op, to_compare=to_compare,
                       if_true=if_true, if_false=if_false)

    def visit_edit1(self, node, children):
        return self._handle_sub(node, children, _VAR_SUBST_EDIT_DELIM1)

    def visit_edit2(self, node, children):
        return self._handle_sub(node, children, _VAR_SUBST_EDIT_DELIM2)

    def _handle_sub(self, node, children, delim):
        '''
        Workhorse function for handling edits.

        :param node:      the node
        :param children:  the node's children
        :param delim:     the delimiter

        :return: an _Edit object
        '''
        var = None
        pattern = None
        repl = ''
        repl_string = None   # original repl string, for errors
        replace_all = False
        flags = 0
        backslash_delim = '\\' + delim
        escaped_group_ref = '\\$'
        referenced_groups = []

        for child in node:
            try:
                expr = child.expr
            except AttributeError:
                continue

            if expr.name == 'identifier':
                var = child.text

            elif expr.name.startswith('pattern'):
                s = child.text.replace(backslash_delim, delim)
                try:
                    pattern = s
                    re.compile(pattern)
                except:
                    raise VariableSubstituterParseError(
                        ('Bad regular expression "{0}" in "{1}".'.format(
                            child.text, node.text
                        ))
                    )

            elif expr.name.startswith('replacement'):
                # The replacement node is an AST consisting of groupref
                # and non_delim tokens. Reassemble them as a Python
                # re.sub()-compliant string, where group references are
                # introduced by backslashes.

                repl_string = child.text
                tokens = []
                for i in child:
                    n = self._find_recursively(i, self.GROUPREF_RE)
                    if n:
                        group = n.text[1:]
                        tokens.append('\\' + group)
                        referenced_groups.append(int(group))
                        continue

                    n = self._find_recursively(i, self.NON_DELIM_RE)
                    if n:
                        s = (
                            n.text
                             .replace(backslash_delim, delim)
                             .replace(escaped_group_ref, '$')
                        )
                        tokens.append(s)
                        continue

                repl = ''.join(tokens)

            elif expr.name == 'flags':
                flag_set = set(child.text)
                if 'i' in flag_set:
                    flags |= re.I
                if 'g' in flag_set:
                    replace_all = True

                leftover = flag_set - {'i', 'g'}
                if len(leftover) > 0:
                    raise VariableSubstituterParseError(
                        'Unknown flag(s) {0} in "{1}"'.format(
                            ', '.join(["'" + c + "'" for c in leftover]),
                            node.text
                        )
                    )

        # Make sure we have all the pieces. Note that "repl" is allowed to
        # be empty.
        if not all_pred(lambda i: i is not None, [var, pattern, repl]):
            raise VariableSubstituterParseError(
                ('(BUG) Unable to find all expected pieces of parsed ' +
                 'substitution expression: "{}". variable={}, pattern={}, ' +
                 'repl={}').format(node.text, var, pattern, repl)
            )

        # Compile the regular expression.
        pattern = re.compile(pattern, flags=flags)
        # Validate the group references.
        total_groups = pattern.groups
        max_group_num = max(referenced_groups) if referenced_groups else 0
        if max_group_num > total_groups:
            raise VariableSubstituterParseError(
                ('Replacement pattern "{0}" refers to non-existent group(s) ' +
                 'in "{1}"').format(repl_string, pattern.pattern)
            )

        return _Edit(variable=var, pattern=pattern, repl=repl,
                     flags=flags, replace_all=replace_all)

    def _find_child(self, node, expr_name):
        for child in node:
            try:
                if child.expr_name == expr_name:
                    return child
            except AttributeError:
                continue

        raise VariableSubstituterParseError(
            '(BUG) Unable to find {}'.format(expr_name)
        )

    def _find_recursively(self, node, expr_re):
        for child in node:
            try:
                if expr_re.search(child.expr_name):
                    return child
            except AttributeError:
                continue

            n = self._find_recursively(child, expr_re)
            if n:
                return n

        return None

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

# ---------------------------------------------------------------------------
# Fire up doctest if main()
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    from doctest import testmod, ELLIPSIS
    testmod(optionflags=ELLIPSIS)
