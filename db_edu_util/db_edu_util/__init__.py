"""
Utility library used by build tools.
"""

VERSION = '1.6.3'

from typing import Callable, Iterable, Any
from textwrap import TextWrapper
import os
import sys
from itertools import dropwhile
from typing import Optional, NoReturn, Generator
import itertools
from contextlib import contextmanager

__all__ = ['all_pred', 'notebooktools', 'databricks', 'EnhancedTextWrapper',
           'die','set_verbosity', 'verbosity_is_enabled', 'wrap2stdout',
           'verbose', 'debug', 'error', 'warn', 'info', 'set_debug',
           'debug_is_enabled', 'working_directory']

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class EnhancedTextWrapper(TextWrapper):
    """
    A version of textwrap.TextWrapper that handles embedded newlines more
    appropriately.
    """
    def __init__(self,
                 width: Optional[int] = None,
                 subsequent_indent: str = ''):
        """

        :param width:             wrap width. Defaults to environment variable
                                  COLUMNS (minus 1), or 79.
        :param subsequent_indent: indent prefix for subsequent lines. Defaults
                                  to empty string.
        """
        if not width:
            columns = os.environ.get('COLUMNS', '80')
            try:
                width = int(columns) - 1
            except ValueError:
                print(
                    f'*** Ignoring non-numeric COLUMNS value of "{columns}"". '
                    'Defaulting to 80.',
                    file=sys.stderr
                )
                os.environ['COLUMNS'] = '80'
                width = 79

        TextWrapper.__init__(self,
                             width=width,
                             subsequent_indent=subsequent_indent)

    def fill(self, msg):
        wrapped = [TextWrapper.fill(self, line) for line in msg.split('\n')]
        return '\n'.join(wrapped)

# -----------------------------------------------------------------------------
# Internal module globals
# -----------------------------------------------------------------------------

_verbose = False
_verbose_wrapper = None
_verbose_prefix = ''
_debug = False
_ERROR_PREFIX = 'ERROR: '
_WARNING_PREFIX = 'WARNING: '
_DEBUG_PREFIX = '(DEBUG) '
try:
    _COLUMNS = int(os.environ.get('COLUMNS', '80')) - 1
except:
    _COLUMNS = 79

_debug_wrapper = EnhancedTextWrapper(
    width=_COLUMNS, subsequent_indent=' ' * len(_DEBUG_PREFIX)
)
_warning_wrapper = EnhancedTextWrapper(
    width=_COLUMNS, subsequent_indent=' ' * len(_WARNING_PREFIX)
)
_error_wrapper = EnhancedTextWrapper(
    width=_COLUMNS, subsequent_indent=' ' * len(_ERROR_PREFIX)
)
_no_prefix_wrapper = EnhancedTextWrapper(width=_COLUMNS)

# -----------------------------------------------------------------------------
# Private Functions
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Public Functions
# -----------------------------------------------------------------------------

def die(msg: str) -> NoReturn:
    """
    Print a message to stderr and abort the program.

    :param msg: the message
    """
    print(_no_prefix_wrapper.fill(msg), file=sys.stderr)
    sys.exit(1)


def set_debug(debug: bool) -> NoReturn:
    """
    Set or clear debug messages.

    :param debug: True or False to enable or disable debug messages
    """
    global _debug

    _debug = debug


def debug_is_enabled() -> bool:
    """
    Determine whether debug messages are on or off.

    :return:  True or False
    """
    return _debug


def set_verbosity(verbose: bool,
                  verbose_prefix: Optional[str] = None) -> NoReturn:
    """
    Set or clear verbose messages.

    :param verbose:        True or False to enable or disable verbosity
    :param verbose_prefix  string to use as a prefix for verbose messages, or
                           None (or empty string) for no prefix
    """
    global _verbose
    global _verbose_prefix
    global _verbose_wrapper

    _verbose = verbose
    if _verbose:
        indent = ''
        if verbose_prefix:
            _verbose_prefix = verbose_prefix
            indent = ' ' * len(verbose_prefix)

        _verbose_wrapper = EnhancedTextWrapper(subsequent_indent=indent)


def verbosity_is_enabled() -> bool:
    """
    Determine whether verbosity is on or off.

    :return:  True or False
    """
    return _verbose


def wrap2stdout(msg: str) -> NoReturn:
    """
    Emit a message to standard output, wrapped at screen boundaries (as
    determined by the COLUMNS environment variable), without any prefix.

    :param msg: The message
    """
    print(_no_prefix_wrapper.fill(msg))


def verbose(msg: str) -> NoReturn:
    """
    Conditionally emit a verbose message. See also set_verbosity().

    :param msg: the message
    """
    if _verbose:
        print(_verbose_wrapper.fill(f"{_verbose_prefix}{msg}"))


def debug(msg: str) -> NoReturn:
    """
    Conditionally emit a debug message.

    :param msg: the message
    """
    if _debug:
        print(_debug_wrapper.fill(f"{_DEBUG_PREFIX}{msg}"))


def warn(msg: str) -> NoReturn:
    """
    Emit a warning message.

    :param msg: The message
    """
    print(_warning_wrapper.fill(f"{_WARNING_PREFIX}{msg}"))


def info(msg: str) -> NoReturn:
    """
    Emit an informational message.

    :param msg: The message
    """
    print(_no_prefix_wrapper.fill(msg))


def error(msg: str) -> NoReturn:
    """
    Emit an error message.

    :param msg: The message
    """
    print(_error_wrapper.fill(f"{_ERROR_PREFIX}{msg}"))


# Regarding the typing: See https://stackoverflow.com/a/49736916/53495
@contextmanager
def working_directory(dir: str) -> Generator[None, None, None]:
    """
    Run a block of code (in a "with" statement) within a specific working
    directory. When the "with" statement ends, cd back to the original
    directory.

    :param dir:  the directory

    :yields: the full path of the directory
    """
    cur = os.getcwd()
    os.chdir(dir)
    try:
        yield os.path.abspath(dir)
    finally:
        os.chdir(cur)


def strip_margin(s: str, margin_char: str = '|') -> str:
    """
    Akin to Scala's stripMargin() method on string, this function takes a
    multiline string and strips leading white space up to a margin character.
    It allows you to express multiline strings like this:

        s = '''|line 1
               |line 2
               |line 3
            '''

    Then, calling strip_margin on the string results in:

        '''line 1
        line 2
        line 3
        '''

    :param s:           the multiline string
    :param margin_char: the margin character, defaulting to '|'

    :return: the stripped string
    """
    assert len(margin_char) == 1
    def fix_line(line: str) -> str:
        adj = ''.join(itertools.dropwhile(lambda c: c in [' ', '\t'], line))
        if (len(adj) > 0) and (adj[0] == margin_char):
            return adj[1:]
        else:
            return adj

    return '\n'.join(map(fix_line, s.split('\n')))


def all_pred(func: Callable[[Any], bool], iterable: Iterable[Any]) -> bool:
    """
    Similar to the built-in `all()` function, this function ensures that
    `func()` returns `True` for every element of the supplied iterable.
    It short-circuits on the first failure.

    :param func:     function or lambda to call with each element
    :param iterable: the iterable

    :return: `True` if all elements pass, `False` otherwise
    False
    """
    for i in iterable:
        if not func(i):
            return False

    return True


def squeeze_blank_lines(s: str) -> str:
    """
    Squeeze multiple blank lines to a single blank line. Also gets rid of
    any leading blank lines.
    """
    saw_blank = False
    if len(s.strip(' \t')) == 0:
        return s.strip(' \t')

    buf = []
    lines = dropwhile(lambda s: len(s.strip()) == 0, s.split('\n'))
    for line in lines:
        line = line.strip()
        if len(line) == 0:
            if saw_blank:
                continue
            saw_blank = True
        else:
            saw_blank = False
        buf.append(line)

    res = '\n'.join(buf)
    if (len(res) > 0) and res[-1] != '\n':
        res += '\n'

    # Edge case: Nothing but blank lines will look, to the above loop, like an
    # empty string. If we had at least one input line, make sure there's a
    # newline.
    if (len(res) == 0):
        res += '\n'

    return res

# ---------------------------------------------------------------------------
# Fire up doctest if main()
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    from doctest import testmod, ELLIPSIS
    testmod(optionflags=ELLIPSIS)
