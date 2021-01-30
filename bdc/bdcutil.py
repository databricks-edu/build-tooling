"""
Utility functions and classes

Run this module as a main program, or run it through `python -m doctest`,
to exercise embedded tests.
"""
from __future__ import annotations  # PEP 563 (allows annotation forward refs)

from abc import ABC, abstractmethod
import re
import os
import contextlib
import markdown2
import shutil
import codecs
import sys
from parsimonious.grammar import Grammar
from parsimonious import grammar, expressions
from parsimonious.exceptions import ParseError, VisitationError
from textwrap import TextWrapper
import mimetypes
from string import Template
from tempfile import TemporaryDirectory
from db_edu_util import all_pred, EnhancedTextWrapper

from typing import (
    Sequence,
    Any,
    Set,
    Optional,
    Dict,
    Tuple,
    Tuple,
    NoReturn,
    Generator,
    Union,
    Pattern,
    Iterable,
    Callable,
    Type,
    no_type_check,
)

__all__ = [
    "read_yaml_file",
    "parse_version_string",
    "flatten",
    "merge_dicts",
    "bool_value",
    "bool_field",
    "find_in_path",
    "ensure_parent_dir_exists",
    "move",
    "joinpath",
    "rm_rf",
    "mkdirp",
    "copy",
    "has_extension",
    "is_html",
    "is_pdf",
    "is_text_file",
    "is_markdown",
    "markdown_to_html",
    "markdown_to_pdf",
    "html_to_pdf",
    "dict_get_and_del",
    "variable_ref_patterns",
    "matches_variable_ref",
    "DefaultStrMixin",
    "VariableSubstituter",
    "VariableSubstituterParseError",
]

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

WARNING_PREFIX = "*** WARNING: "
DEBUG_PREFIX = "(DEBUG) "

# ---------------------------------------------------------------------------
# Module globals
# ---------------------------------------------------------------------------

_verbose = False
_verbose_prefix = ""

# Text wrappers
_warning_wrapper = EnhancedTextWrapper(subsequent_indent=" " * len(WARNING_PREFIX))

_verbose_wrapper = EnhancedTextWrapper()

_error_wrapper = EnhancedTextWrapper()

_info_wrapper = EnhancedTextWrapper(subsequent_indent=" " * 4)

_debug_wrapper = EnhancedTextWrapper(subsequent_indent=" " * len(DEBUG_PREFIX))

_generic_wrapper = EnhancedTextWrapper()

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def read_yaml_file(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    Load the specified YAML file, handling any include preprecessing.

    :param path:     the path to the file
    :param encoding: the encoding to use

    :return: the loaded YAML file
    """
    from io import StringIO
    from grizzled.file.includer import Includer
    import yaml

    inc = Includer(source=path, include_regex=r'#include\s+"([^"]+)"', encoding="utf-8")
    input = StringIO("".join([line for line in inc]))
    return yaml.safe_load(input)


def parse_version_string(version: str) -> Tuple[int, int]:
    """
    Parse a semantic version string (e.g., 1.10.30) or a partial
    <major>.<minor> semver string (e.g., 1.10) into a tuple of
    (major, minor, patch) or (major, minor) integers. Raises ValueError for
    a malformed version string. The patch level (third number) is ignored

    :param version:  the string to parse

    :return:  A `(major, minor)` tuple of ints.
    """
    nums = version.split(".")
    if len(nums) not in (2, 3):
        raise ValueError(f'"{version}" is a malformed version string')
    try:
        if "-" in nums[-1]:
            nums[-1], _ = nums[-1].split("-")
        return tuple([int(i) for i in nums])[0:2]
    except ValueError as e:
        raise ValueError(f'"{version}" is a malformed version string: {e}')


def flatten(it: Iterable[Any]) -> Generator[Any, Any, None]:
    """
    Recursively flatten an iterable. Yields a generator for a new iterable.

    NOTE: This function explicitly does NOT treat strings as iterables, even
    though they are.

    :param it: the iterable to flatten

    :return: a generator for the recursively flattened result
    """

    # Special case for strings: Since a string is iterable, but cannot be
    # nested, and since looping over it produces single-character strings,
    # which themselves are iterable (leading to infinite recursion), strings
    # must be handled specially.
    if type(it) is str:
        yield it

    else:
        for i in it:
            if type(i) is str:
                yield i
                continue

            try:
                # Is this thing iterable?
                for j in flatten(iter(i)):
                    yield j
            except TypeError:
                # No. Just yield it as is.
                yield i


def merge_dicts(
    dict1: Dict[str, Any], dict2: Dict[str, Any], *dicts: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge multiple dictionaries, producing a merged result without modifying
    the arguments.

    :param dict1:  the first dictionary
    :param dict2:  the second dictionary
    :param dicts:  additional dictionaries

    :return: The merged dictionary. Keys in dict2 overwrite duplicate keys in
             dict1
    """
    res = dict1.copy()
    res.update(dict2)
    for d in dicts:
        res.update(d)
    return res


def bool_value(s: Union[str, int]) -> bool:
    """
    Convert a string or int to a boolean value. Raises ValueError if the string
    isn't boolean.

    :param s: the string

    :return: the boolean
    """
    if isinstance(s, bool):
        return s

    if isinstance(s, int):
        return False if s == 0 else True

    sl = s.lower()
    if sl in ("t", "true", "1", "yes"):
        return True
    elif sl in ("f", "false", "0", "no"):
        return False
    else:
        raise ValueError(f'Bad boolean value: "{s}"')


def bool_field(d: Dict[str, Any], key: str, default: bool = False) -> bool:
    """
    Get a boolean value from a dictionary, parsing it if it's a string.

    :param d:       the dictionary
    :param key:     the key
    :param default: the default, if not found

    :return: the value

    :raise ValueError on error
    """
    return bool_value(d.get(key, default))


def find_in_path(command: str) -> str:
    """
    Find a command in the path, or bail.

    :param command:  the command to find
    :return: the location. Throws an exception otherwise.
    """
    path = [p for p in os.getenv("PATH", "").split(os.pathsep) if len(p) > 0]
    for d in path:
        p = os.path.join(d, command)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    else:
        raise Exception(f"""Can't find "{command}" in PATH.""")


def ensure_parent_dir_exists(path: str) -> NoReturn:
    """
    Ensures that the parent directory of a path exists.

    :param path: The path whose parent directory must exist.
    """
    mkdirp(os.path.dirname(path))


def move(
    src: str, dest: str, ensure_final_newline: bool = False, encoding: str = "UTF-8"
) -> NoReturn:
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
    _do_copy(src, dest, ensure_final_newline=ensure_final_newline, encoding=encoding)
    os.unlink(src)


def joinpath(*pieces: str) -> str:
    """
    Similar to os.path.join(), this function joins the path components, but
    also normalizes the path.

    :param pieces: the path pieces

    :return: the joined an normalized path
    """
    return os.path.normpath(os.path.join(*pieces))


def rm_rf(path: str) -> NoReturn:
    """
    Equivalent of "rm -rf dir", this function is similar to
    shutil.rmtree(dir), except that it doesn't abort if the directory does
    not exist. It also silently handles regular files. This function throws
    an OSError if the passed file is neither a regular file nor a directory.

    :param path: The directory or file to (recursively) remove, if it
                        exists.
    """
    if os.path.exists(path):
        if os.path.isfile(path):
            os.unlink(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            raise OSError(f'"{path}" is neither a file nor a directory')


def mkdirp(dir: str) -> NoReturn:
    """
    Equivalent of "mkdir -p". This function is just a front-end to
    `os.makedirs()`, but it doesn't abort if the directory already exists.

    :param dir: The directory to be created, along with any intervening
                parent directories that don't exist.
    """
    if not os.path.exists(dir):
        os.makedirs(dir)


def copy(
    src: str, dest: str, ensure_final_newline: bool = False, encoding: str = "UTF-8"
) -> NoReturn:
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
    _do_copy(src, dest, ensure_final_newline=ensure_final_newline, encoding=encoding)


def has_extension(path: str) -> bool:
    """
    Simple convenience function that uses os.path.splitext() to determine
    whether a file has an extension or not.

    :param path: the path

    :return: True or False
    """
    (_, ext) = os.path.splitext(path)
    return (ext is not None) and (len(ext) > 0)


def is_text_file(path: str) -> bool:
    """
    Determine whether a file is a text file or not. This determination is
    based solely on its MIME type, which is based off the file extension.

    :param path: the path to the file

    :return: True or False
    """
    is_text = False
    if is_html(path) or is_markdown(path):
        is_text = True
    else:
        (mime_type, _) = mimetypes.guess_type(path)

        if (mime_type is not None) and ("/" in mime_type):
            (major, _) = os.path.splitext(path)
            is_text = major == "text"
    return is_text


def is_pdf(path: str) -> bool:
    """
    Determine whether a file is a PDF file or not. This determination is made
    solely on the MIME type, which is based off the file extension.

    :param path: the path to the file

    :return: True or False
    """
    (mime_type, _) = mimetypes.guess_type(path)
    return mime_type == "application/pdf"


def is_html(path: str) -> bool:
    """
    Determine whether a file is an HTML file or not.

    :param path: the path to the file

    :return: True or False
    """
    import mimetypes

    (mime_type, _) = mimetypes.guess_type(path)
    return mime_type in ("application/xhtml+xml", "text/html")


def is_markdown(path: str) -> bool:
    """
    Determine whether a file is a Markdown file or not.

    :param path: the path to the file

    :return: True or False
    """
    (_, extension) = os.path.splitext(path)
    return extension.lower() in [".md", ".markdown"]


def markdown_to_html(
    markdown: str,
    html_out: str,
    html_template: Optional[str] = None,
    stylesheet: Optional[str] = None,
) -> NoReturn:
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
    with codecs.open(markdown, mode="r", encoding="UTF-8") as input:
        text = input.read()
        body = markdown2.markdown(
            text, extras=["fenced-code-blocks", "tables", "header-ids"]
        )
        if stylesheet is None:
            stylesheet = DEFAULT_CSS

        if html_template is None:
            html_template = DEFAULT_HTML_TEMPLATE

        template = Template(html_template)

        with codecs.open(html_out, mode="w", encoding="UTF-8") as output:
            output.write(
                template.substitute(
                    body=body, title=os.path.basename(markdown), css=stylesheet
                )
            )


def html_to_pdf(html: str, pdf_out: str) -> NoReturn:
    """
    Convert an HTML document to PDF, writing it to the specified PDF file.

    :param html:     the path to the HTML file
    :param pdf_out:  the output PDF file
    """
    import warnings

    # Ignore user warnings emitted by the WeasyPrint package.
    # See https://docs.python.org/3/library/warnings.html#temporarily-suppressing-warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from weasyprint import HTML

        dom = HTML(filename=html)
        dom.write_pdf(pdf_out)


def markdown_to_pdf(
    markdown: str,
    pdf_out: str,
    html_template: Optional[str] = None,
    stylesheet: Optional[str] = None,
) -> NoReturn:
    """
    Convert a Markdown file to PDF, writing it to the specified PDF file.
    If the stylesheet is specified, it is inserted.

    :param markdown:      The path to the Markdown file
    :param pdf_out        The path to the desired PDF output file
    :param html_template  A template for the full HTML, or None to use the
                          default.
    :param stylesheet     A string containing a stylesheet to inline, or None
                          to use the default
    """
    with TemporaryDirectory() as tempdir:
        html = os.path.join(tempdir, "out.html")
        markdown_to_html(markdown, html, html_template, stylesheet)
        html_to_pdf(html, pdf_out)


def dict_get_and_del(d: Dict[str, Any], key: str, default: Optional[Any] = None) -> Any:
    """
    Get the value of a key from a dictionary, and remove the key.

    :param d:        the dictionary
    :param key:      the key
    :param default:  the default value, if the key isn't present

    :return: The value, with d possibly modified
    """
    if key in d:
        res = d[key]
        del d[key]
        return res

    return default


def variable_ref_patterns(variable_name: str) -> Sequence[Pattern]:
    """
    Convert a variable name into a series of regular expressions that will
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
    """
    return (
        re.compile(r"^(.*)(\$\{" + variable_name + r"\})(.*)$"),
        re.compile(r"^(.*)(\$\{" + variable_name + r"\[\d*:?\d*\]\})(.*)$"),
        re.compile(r"^(.*)(\$" + variable_name + r")([^a-zA-Z_]+.*)$"),
        re.compile(r"^(.*)(\$" + variable_name + r")()$"),  # empty group 3
        # This next bit of ugliness matches the ternary IF syntax
        re.compile(
            r"^(.*)(\${"
            + variable_name
            + r'\s*[=!]=\s*"[^}?:]*"\s*\?\s*"[^}?:]*"\s*:\s*"[^}?:]*"})(.*)$'
        ),
        # And this one matches the edit syntax.
        re.compile(
            r"^(.*)(\${" + variable_name + "[/|][^/|]*[/|][^/|]*[/|][ig]?})(.*)$"
        ),
    )


def matches_variable_ref(
    patterns: Sequence[Pattern], string: str
) -> Optional[Sequence[str]]:
    """
    Matches the string against the patterns, returning a 3-tuple on match and
    None on no match.

    :param patterns: A series of patterns returned from variable_ref_patterns().
    :param string:   The string against which to match.

    :return: None if no match. If match, a 3-tuple containing three elements:
             the portion of the string preceding the variable reference,
             the variable reference, and the portion of the string following
             the variable reference
    """

    for p in patterns:
        m = p.match(string)
        if m:
            return m.groups()
    else:
        return None


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------


class DefaultStrMixin(ABC):
    """
    Provides default implementations of __str__() and __repr__(). These
    implementations assume that all arguments passed to the constructor are
    captured in same-named fields in `self`.
    """

    def __str__(self):
        indent = " " * (len(self.__class__.__name__) + 1)
        fields = []
        for key in sorted(self.__dict__.keys()):
            value = self.__dict__[key]
            v = f'"{value}"' if isinstance(value, str) else value
            fields.append(f"{key}={v}")

        delim = f",\n{indent}"
        class_name = self.__class__.__name__
        field_str = delim.join(fields)
        return f"{class_name}({field_str})"

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
#
# If you make ANY changes to the grammar, (a) run the doctests, and (b) write
# more doctests.
#
# GRAMMAR DEBUGGING HINTS:
#
# 1. Parsimonious produces its own complicated AST when it parses a string
#    with this grammar. Printing that AST (via a tactical print statement in
#    the VariableSubstituter constructor) can help.
# 2. The _VarSubstASTVisitor class is custom Parsimonious visitor that
#    traverses the Parsimonious AST and converts it into a sequence of tokens
#    for easier processing. (Those tokens include _Var, _Text, _Edit and
#    _Ternary objects.) Printing that token stream can also help.
# 3. The _VarSubstASTVisitor class's methods do a lot of work, and they're
#    highly dependent on (coupled to) the grammar. Print statements in those
#    methods are also helpful.
# 4. When doctests fail, the errors aren't always as helpful as if the same
#    failure occurred outside of doctest. Run the same test inside the REPL.
#    You'll get more detailed errors.

_VAR_SUBST_EQ_OP = "=="
_VAR_SUBST_NE_OP = "!="

_VAR_SUBST_OPS = {  # the supported ternary expression operators
    _VAR_SUBST_EQ_OP,
    _VAR_SUBST_NE_OP,
}

_VAR_SUBST_VAR_PREFIX = "$"
_VAR_SUBST_ESCAPED_VAR_PREFIX = _VAR_SUBST_VAR_PREFIX + _VAR_SUBST_VAR_PREFIX
_VAR_SUBST_EDIT_DELIM1 = "/"
_VAR_SUBST_EDIT_DELIM2 = "|"
_VAR_SUBST_EDIT_GROUPREF_PREFIX = "$"


def _replace_tokens(s: str, tokens: Dict[str, str]) -> str:
    s2 = s
    for token, replacement in list(tokens.items()):
        s2 = s2.replace(token, replacement)
    return s2


# The grammar itself. Some values are substituted, so they can be shared
# with the code.
_VAR_SUBST_OPS_RULE = " / ".join([f'"{op}"' for op in _VAR_SUBST_OPS])
_VAR_SUBST_GRAMMAR = _replace_tokens(
    r"""
# A line consists of zero or more terms. 
line                  = term*

# A term consists of an edit or a ternary expression or a variable substitution
# or text. Order is important here, since first match wins.
term                  = edit / ternary / var / text

# Two forms of variable references are permitted: $var and ${var}
var                   = var1 / var2
var1                  = var_prefix (!var_prefix identifier) 
var2                  = full_var_prefix 
                        (!var_prefix identifier)
                        subscript? 
                        full_var_suffix

subscript_start_op    = '['
subscript_end_op      = ']'

index                 = '-'? digit+
slice_start           = index
slice_end             = index

index_sep             = ':'
subscript             = subscript_start_op !subscript_start_op
                        ( (index index_sep index)
                        / (index index_sep)
                        / (index_sep index)
                        / index_sep
                        / index
                        )
                        subscript_end_op
                        
full_var_prefix       = "${"
full_var_suffix       = '}'
var_prefix            = @VAR_PREFIX@

backslash             = '\\'
char                  = ~"."

# Only double quotes are permitted in quoted strings.
quote                 = '"'

# Ternary IF. Format:
# 
#    ${var == "SOMESTRING" ? "TRUESUB" : "FALSESUB"}
#    ${var != "SOMESTRING" ? "TRUESUB" : "FALSESUB"}

ternary               = full_var_prefix
                        identifier OPT_WS
                        compare_op OPT_WS
                        ternary_compare_term OPT_WS
                        ternary_op OPT_WS
                        ternary_true_side OPT_WS
                        ternary_else OPT_WS
                        ternary_false_side
                        full_var_suffix
ternary_true_side     = quote var_or_text* quote
ternary_false_side    = quote var_or_text* quote
ternary_compare_term  = quote var_or_text* quote

var_or_text           = var / text

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
edit1                 = full_var_prefix
                        identifier
                        edit_delim1
                        pattern1
                        edit_delim1
                        replacement1
                        edit_delim1
                        flags
                        full_var_suffix
edit2                 = full_var_prefix
                        identifier
                        edit_delim2
                        pattern2
                        edit_delim2
                        replacement2
                        edit_delim2
                        flags
                        full_var_suffix
flags                 = (~"[ig]"i)*

# NOTE: "!" is a negative lookahead assertion: It asserts that the token isn't
# present, but doesn't consume anything. Thus, "!quote" asserts that the first
# character isn't a quote, but doesn't consume it, so it'll get picked up
# by "char".  

edit_delim1           = @EDIT_DELIM_1@
non_edit_delim1       = ( (backslash edit_delim1) 
                        / (backslash groupref_prefix)
                        / (!edit_delim1 char)
                        )
pattern1              = non_edit_delim1+
replacement1          = (groupref / var / non_edit_delim1)*

edit_delim2           = @EDIT_DELIM_2@
non_edit_delim2       = ( (backslash edit_delim2)
                        / (backslash groupref_prefix)
                        / (!edit_delim2 char)
                        )
pattern2              = non_edit_delim2+
replacement2          = (groupref / var / non_edit_delim2)*

groupref_prefix       = @EDIT_GROUPREF_PREFIX@
groupref              = (!backslash groupref_prefix digit)

digit                 = ~"\d"
identifier            = ~"[A-Z0-9_]+"i
non_var               = ( (backslash var_prefix)
                        / (backslash ~"[\"]")
                        / (var_prefix var_prefix)
                        / ~"[^$\"]" 
                        )
text                  = non_var*
OPT_WS                = ~"\s*"
""",
    {
        "@OPS@": _VAR_SUBST_OPS_RULE,
        "@EDIT_DELIM_1@": "'" + _VAR_SUBST_EDIT_DELIM1 + "'",
        "@EDIT_DELIM_2@": "'" + _VAR_SUBST_EDIT_DELIM2 + "'",
        "@EDIT_GROUPREF_PREFIX@": "'" + _VAR_SUBST_EDIT_GROUPREF_PREFIX + "'",
        "@VAR_PREFIX@": "'" + _VAR_SUBST_VAR_PREFIX + "'",
    },
)

# print(_VAR_SUBST_GRAMMAR);import sys;sys.exit(1)


class VariableSubstituterParseError(Exception):
    pass


class VariableSubstituter(object):
    """
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
    """

    def __init__(self, template: str):
        """
        Create a new variable substituter.

        :param template: The template containing variables to substitute.
        """
        self._template = template
        try:
            self._grammar = Grammar(_VAR_SUBST_GRAMMAR)
            parsimonious_ast = self._grammar.parse(template)
            visitor = _VarSubstASTVisitor()
            self._tokens = list(flatten(visitor.visit(parsimonious_ast)))

        except ParseError as e:
            raise VariableSubstituterParseError(
                f'Failed to parse "{self.template}": {e}'
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
            pat = re.compile(r"^.*VariableSubstituterParseError: (.*)\s*Parse tree:")
            msg = str(e).replace("\n", " ")
            m = pat.search(msg)
            if m:
                raise VariableSubstituterParseError(
                    f'Failed to parse "{self.template}: {m.group(1)}'
                )
            else:
                raise VariableSubstituterParseError(
                    f'Failed to parse "{self.template}"'
                )

    @property
    def template(self) -> str:
        """
        Get the template.

        :return:  the template string
        """
        return self._template

    def substitute(self, variables: Dict[str, Any]) -> str:
        """
        Substitute all variable references and ternary IFs in the template,
        using the supplied variables. This method will throw an `KeyError` if
        it encounters any variable reference that isn't in the supplied
        dictionary.

        :param variables: A dictionary of variable name to value mappings

        :return: The substituted string
        """

        def get_var(varname):
            return str(variables[varname])

        return self._subst(get_var)

    def safe_substitute(self, variables: Dict[str, Any]) -> str:
        """
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
        """

        def get_var(varname):
            return str(variables.get(varname, ""))

        return self._subst(get_var)

    def _subst(self, get_var: Callable[[str], Any]) -> str:
        """
        Workhorse method for both substitute() and safe_substitute().

        :param get_var:  function to call to retrieve a variable's value

        :return: The substituted string
        """

        def handle_token(token):
            if type(token) is _Var:
                result = token.evaluate(get_var(token.name))
            elif type(token) == _Text:
                result = token.text
            elif type(token) == _Ternary:
                result = token.evaluate(get_var)
            elif type(token) == _Edit:
                result = token.evaluate(get_var)
            else:
                raise KeyError(f"(BUG) Unknown token: {token}")

            return result

        return "".join([t.evaluate(get_var) for t in self._tokens])


class _Token(DefaultStrMixin):
    """
    Abstract base class for tokens generated from the Parsimionious AST.
    implementations assume that all arguments passed to the constructor are
    captured in same-named fields in `self`.
    """

    @abstractmethod
    def evaluate(self, get_var: Callable[[str], Any]) -> str:
        """
        Evaluate the token, returning the resulting string.

        :param get_var: A function that will retrieve the value of a variable

        :return: the expanded string
        """
        pass

    def _expand(
        self,
        get_var: Callable[[str], Any],
        tokens: Sequence[Type[_Token]],
        allowed_tokens: Set[Type[_Token]],
    ) -> str:
        """
        Expands a list of tokens, processing each one by calling its
        evaluate() method.

        :param get_var         a function that will retrieve the value of a
                               variable
        :param tokens:         the list of tokens
        :param allowed_tokens: the set of allowed token classes; any others are
                               ignored

        :return: the resulting string
        """
        return "".join(
            [t.evaluate(get_var) for t in tokens if t.__class__ in allowed_tokens]
        )


class _Var(_Token):
    """
    Captures a variable name in the modified (i.e., non-Parsimonious) AST.
    """

    def __init__(
        self,
        name: str,
        slice_start: Optional[int] = None,
        slice_end: Optional[int] = None,
    ):
        """
        Create a new variable reference.

        :param name:        the variable name
        :param slice_start: starting subscript, if any. None if not.
        :param slice_end:   ending subscript, if any. None if not.
        """
        super(_Var, self).__init__()
        self.name = name
        self.slice_start = slice_start
        self.slice_end = slice_end

    def evaluate(self, get_var: Callable[[str], Any]) -> str:
        """
        Evaluate the variable's value, applying any subscripts.

        :param get_var: A function that will retrieve the value of a variable

        :return: the possibly-sliced value
        """
        v = str(get_var(self.name))
        if len(v) == 0:
            return ""

        if self.slice_start is None:  # No subscripts.
            return v

        if self.slice_end is None:  # One subscript
            i = len(v) - 1 if self.slice_start > len(v) else self.slice_start
            return v[i]

        end = len(v) if self.slice_end > len(v) else self.slice_end
        return v[self.slice_start : end]


class _Text(_Token):
    """
    Captures arbitrary text in the modified (i.e., non-Parsimonious) AST.
    """

    def __init__(self, text: str):
        """
        Create a new text container.

        :param text: the contents of the text
        """
        super(_Text, self).__init__()
        self.text = text

    def evaluate(self, get_var: Callable[[str], Any]) -> str:
        """
        Evaluate the token. In this case, just return the text

        :param get_var: A function that will retrieve the value of a variable

        :return: the text
        """
        return self.text


class _Ternary(_Token):
    """
    Captures the pieces of a ternary IF.
    """

    def __init__(
        self,
        variable: str,
        op: str,
        to_compare: Optional[Sequence[Type[_Token]]],
        if_true: Optional[Sequence[Type[_Token]]],
        if_false: Optional[Sequence[Type[_Token]]],
    ):
        """
        Create a new _Ternary object.

        :param variable:    the variable to substitute and test
        :param op:          the operation (one of OPS)
        :param to_compare:  the string (token) against which to compare the
                            variable
        :param if_true:     the string (token) to substitute if the comparison
                            is true
        :param if_false:    the string (token) to substitute if the comparison
                            is false
        """
        super(_Ternary, self).__init__()
        self.variable = variable
        self.op = op
        self.to_compare = to_compare
        self.if_true = if_true
        self.if_false = if_false

    def evaluate(self, get_var: Callable[[str], Any]) -> str:
        """
        Evaluate the ternary expression, returning the resulting string.

        :param get_var: A function that will take a variable name and retrieve
                        its value
        :return: the resulting string
        """

        to_compare = self._expand(get_var, self.to_compare, {_Var, _Text})

        this_var_value = get_var(self.variable)
        if self.op == _VAR_SUBST_EQ_OP:
            test = to_compare == this_var_value
        else:
            test = to_compare != this_var_value

        if test is True:
            return self._expand(get_var, self.if_true, {_Var, _Text})
        else:
            return self._expand(get_var, self.if_false, {_Var, _Text})


class _Edit(_Token):
    """
    Stores the pieces of an inline variable value edit.
    """

    def __init__(
        self, variable: str, pattern: Pattern, repl: str, replace_all: bool = False
    ):
        """
        Create a new _Edit token.

        :param variable:    the variable whose value is to be edited
        :param pattern:     the regular expression to find and substitute
        :param repl:        the replacement tokens (a list of _Text and _Var
                            objects)
        :param replace_all: whether to not to do a global replacement
        """
        super(_Edit, self).__init__()
        self.variable = variable
        self.pattern = pattern
        self.repl = repl
        self.replace_all = replace_all

    def evaluate(self, get_var: Callable[[str], Any]) -> str:
        """
        Evaluate the edit expression, returning the resulting string.

        :param get_var: A function that will take a variable name and retrieve
                        its value
        :return: the resulting string
        """
        value = str(get_var(self.variable))

        # Expand the replacement string.
        repl = self._expand(get_var, self.repl, {_Var, _Text})
        count = 0 if self.replace_all else 1
        return self.pattern.sub(repl, value, count=count)


@no_type_check
class _VarSubstASTVisitor(grammar.NodeVisitor):
    """
    Node visitor, which translates the Parsimonious AST to a list of tokens.
    """

    GROUPREF_RE = re.compile(r"^groupref$")
    NON_DELIM_RE = re.compile(r"^non_edit_delim\d$")
    SUBSCRIPT_RE = re.compile(r"^subscript$")
    IDENT_RE = re.compile(r"^identifier$")

    """
    This visitor translates the parsed Parsimonious AST into something more
    useful to the template substituter.
    """

    def generic_visit(self, node, visited_children):
        """
        Called to visit any other node. This method must be here, or the
        visit logic will bail. This code is adapted from code within
        Parsimonious. Basically, if the node has children, we replace the
        node with its children. Otherwise, we return the node.

        :param node:              the node
        :param visited_children:  its children

        :return: the node or its children
        """
        return visited_children or node

    def visit_var1(self, node, children):
        """
        Called to visit "var1" nodes

        :param node:     the node
        :param children: any related children

        :return: A `_Var` object
        """
        return _Var(node.text[1:])

    def visit_var2(self, node, children):
        """
        Called to visit "var2" nodes

        :param node:     the node
        :param children: any related children

        :return: A `_Var` object
        """
        sub_node = self._find_recursively(node, self.SUBSCRIPT_RE)
        slice_nums = [None, None]
        if sub_node:
            tokens = [
                n.text
                for n in self._all_descendent_exprs(sub_node)
                if n.expr.name in ("index", "index_sep")
            ]
            # Convert the whole thing into a pattern, for easy matching.
            pat = ""
            for t in tokens:
                pat += ":" if t == ":" else "n"

            if pat == ":":
                # ${var[:]} is the same as ${var}
                pass
            elif pat == "n:":
                slice_nums = [int(tokens[0]), sys.maxsize]
            elif pat == ":n":
                slice_nums = [0, int(tokens[1])]
            elif pat == "n":
                slice_nums = [int(tokens[0]), None]
            elif pat == "n:n":
                slice_nums = [int(tokens[0]), int(tokens[2])]
            else:
                token_str = "".join(tokens)
                raise VariableSubstituterParseError(
                    f'(BUG) Unrecognized slice pattern "{token_str}" in '
                    + f'"{node.text}".'
                )

        var_name = self._find_recursively(node, self.IDENT_RE)
        return _Var(var_name.text, *slice_nums)

    def visit_text(self, node, children):
        """
        Called to visit text nodes.

        :param node:     the node
        :param children: any related children

        :return: a `_Text` object
        """
        # Be sure to unescape stuff.
        def unescape(s):
            s2 = ""
            saw_backslash = False
            for c in s:
                if saw_backslash:
                    if c in {_VAR_SUBST_VAR_PREFIX, "\\", '"'}:
                        s2 += c
                    else:
                        s2 += "\\" + c
                    saw_backslash = False
                    continue

                if c == "\\":
                    saw_backslash = True
                    continue

                s2 += c

            return s2

        # Also handle "$$" as a special caswe.
        return _Text(
            unescape(node.text).replace(
                _VAR_SUBST_ESCAPED_VAR_PREFIX, _VAR_SUBST_VAR_PREFIX
            )
        )

    def visit_ternary(self, node, children):
        """
        Called to visit a ternary IF reference.

        :param node:     The node
        :param children: Its children

        :return: A `_Ternary` object.
        """
        # This is somewhat complicated, as it needs to handle multiple tokens.
        # Looping over the children is safer than direct indexing, and it's
        # less likely to break when the grammar is slightly modified.
        # Here, we simply loop through the node itself, which will give us
        # children the next level down (i.e., directly under the "ternary"
        # node). We match against those nodes, and find *their* children as
        # necessary.
        #
        # THIS CODE IS COUPLED TIGHTLY TO THE GRAMMAR.

        def var_or_text_nodes(node):
            res = []
            for c in self._all_descendent_exprs(node):
                name = c.expr.name
                if name == "text":
                    res.append(self.visit_text(c, []))
                elif name == "var1":
                    res.append(self.visit_var1(c, []))
                elif name == "var2":
                    res.append(self.visit_var2(c, []))

            return res

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

            if expr.name == "identifier":
                # The only identifier token here is the variable.
                var = child.text

            elif child.text in _VAR_SUBST_OPS:
                # Capture the comparison operation.
                op = child.text

            elif expr.name == "ternary_compare_term":
                to_compare = var_or_text_nodes(child)

            elif expr.name == "ternary_true_side":
                if_true = var_or_text_nodes(child)

            elif expr.name == "ternary_false_side":
                if_false = var_or_text_nodes(child)

        if not all_pred(
            lambda i: i is not None, [var, op, to_compare, if_true, if_false]
        ):
            raise VariableSubstituterParseError(
                "(BUG) Unable to find all expected pieces of parsed ternary "
                + f'expression: "{node.text}". var={var}, op={op}, '
                + f"to_compare={to_compare}, if_true={if_true}, "
                + f"if_false={if_false}"
            )
        return _Ternary(
            variable=var,
            op=op,
            to_compare=to_compare,
            if_true=if_true,
            if_false=if_false,
        )

    def visit_edit1(self, node, children):
        """
        Processes an 'edit1' node.

        :param node:      the node
        :param children:  its children

        :return: the tokens
        """
        return self._handle_sub(node, children, _VAR_SUBST_EDIT_DELIM1)

    def visit_edit2(self, node, children):
        """
        Processes an 'edit2' node.

        :param node:      the node
        :param children:  its children

        :return: the tokens
        """
        return self._handle_sub(node, children, _VAR_SUBST_EDIT_DELIM2)

    def _handle_sub(self, node, children, delim):
        """
        Workhorse function for handling edits.

        :param node:      the node
        :param children:  the node's children
        :param delim:     the delimiter

        :return: an _Edit object
        """

        def parse_replacement(child):
            # The replacement node is an AST consisting of groupref,
            # variable, and non_delim tokens. Reassemble them as a Python
            # re.sub()-compliant string, where group references are
            # introduced by backslashes.

            repl_string = child.text
            tokens = []
            for n in self._all_descendent_exprs(child):
                if self.GROUPREF_RE.match(n.expr.name):
                    group = n.text[1:]
                    tokens.append(_Text("\\" + group))
                    referenced_groups.append(int(group))
                    continue

                if self.NON_DELIM_RE.match(n.expr.name):
                    s = n.text.replace(backslash_delim, delim).replace(
                        escaped_group_ref, "$"
                    )
                    tokens.append(_Text(s))
                    continue

                if n.expr.name == "var1":
                    tokens.append(self.visit_var1(n, []))
                    continue

                if n.expr.name == "var2":
                    tokens.append(self.visit_var2(n, []))
                    continue

            return tokens

        # Main method logic

        var = None
        pattern = None
        repl = ""
        repl_string = None  # original repl string, for errors
        replace_all = False
        flags = 0
        backslash_delim = "\\" + delim
        escaped_group_ref = "\\$"
        referenced_groups = []

        for child in self._child_exprs(node):
            expr = child.expr
            if expr.name == "identifier":
                var = child.text

            elif expr.name.startswith("pattern"):
                try:
                    pattern = child.text.replace(backslash_delim, delim)
                    re.compile(pattern)
                except:
                    raise VariableSubstituterParseError(
                        f'Bad regular expression "{child.text}" in ' + f'"{node.text}".'
                    )

            elif expr.name.startswith("replacement"):
                repl = parse_replacement(child)

            elif expr.name == "flags":
                flag_set = set(child.text)
                if "i" in flag_set:
                    flags |= re.I
                if "g" in flag_set:
                    replace_all = True

                leftover = flag_set - {"i", "g"}
                if len(leftover) > 0:
                    flag_str = ", ".join(["'" + c + "'" for c in leftover])
                    raise VariableSubstituterParseError(
                        f'Unknown flag(s) {flag_str} in "{node.text}"'
                    )

        # Make sure we have all the pieces. Note that "repl" is allowed to
        # be empty.
        if not all_pred(lambda i: i is not None, [var, pattern, repl]):
            raise VariableSubstituterParseError(
                "(BUG) Unable to find all expected pieces of parsed "
                + f'substitution expression: "{node.text}". variable={var}, '
                + f"pattern={pattern}, repl={repl}"
            )

        # Compile the regular expression.
        pattern = re.compile(pattern, flags=flags)

        # Validate the group references.
        total_groups = pattern.groups
        max_group_num = max(referenced_groups) if referenced_groups else 0
        if max_group_num > total_groups:
            raise VariableSubstituterParseError(
                f'Replacement pattern "{repl_string}" refers to non-existent '
                + f'group(s) in "{pattern.pattern}"'
            )

        return _Edit(variable=var, pattern=pattern, repl=repl, replace_all=replace_all)

    def _child_exprs(self, node):
        """
        Return a generator of all of a node's immediate child nodes that have
        an `expr` field.

        :param node: the node

        :return: the child nodes
        """
        for child in node:
            if hasattr(child, "expr"):
                yield child

    def _all_descendents(self, node):
        """
        Return a generator of all of a node's descendents.

        :param node: the node

        :return: the descendent nodes
        """
        for child in node:
            yield child
            for c in self._all_descendents(child):
                yield c

    def _all_descendent_exprs(self, node):
        """
        Return a generator of all of a node's descendents that have an
        `expr` field.

        :param node: the node

        :return: the descendent nodes
        """
        for child in self._all_descendents(node):
            if hasattr(child, "expr"):
                yield child

    def _find_recursively(self, node, expr_re):
        """
        Search all of a node's descendents for the ones that have an `expr_name`
        that matches the specified regular expression.

        :param node:     the node
        :param expr_re:  the compiled regular expression

        :return: the matching nodes
        """
        for child in self._all_descendents(node):
            try:
                if expr_re.search(child.expr_name):
                    return child
            except AttributeError:
                continue

        return None


# ---------------------------------------------------------------------------
# Module-private functions
# ---------------------------------------------------------------------------


def _do_copy(
    src: str, dest: str, ensure_final_newline: bool = False, encoding: str = "UTF-8"
):
    """
    Workhorse function that actually copies a text file. Used by move() and
    copy(). The source file's mode and other stats are copied, as well as its
    contents.

    :param src:                    the path to the file to be copied.
    :param dest:                   the path to the target, which is assumed
                                   to be a file, not a directory
    :param ensure_final_newline:   True to ensure that the copied file has a
                                   final newline, False to simply copy it as
                                   is
    :param encoding:               the encoding of the source file

    :raise IOError: On error
    """
    if not os.path.exists(src):
        raise IOError(f'"{src}" does not exist.')

    src = os.path.abspath(src)
    dest = os.path.abspath(dest)
    ensure_parent_dir_exists(dest)

    if not ensure_final_newline:
        shutil.copy2(src, dest)
    else:
        with codecs.open(src, mode="r", encoding=encoding) as input:
            with codecs.open(dest, mode="w", encoding=encoding) as output:
                last_line_had_nl = False
                for line in input:
                    output.write(line)
                    last_line_had_nl = line[-1] == "\n"
                if not last_line_had_nl:
                    output.write("\n")
        shutil.copystat(src, dest)


# ---------------------------------------------------------------------------
# Fire up doctest if main()
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from doctest import testmod, ELLIPSIS

    testmod(optionflags=ELLIPSIS)
