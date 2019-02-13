"""
Utility library used by build tools.
"""

VERSION = '1.2.0'

from typing import Callable, Iterable, Any
from textwrap import TextWrapper
import os
import sys
from typing import Optional

__all__ = ['all_pred', 'notebooktools', 'db_cli', 'EnhancedTextWrapper']

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
                    f'*** Ignoring non-numeric value of COLUMNS ({columns})',
                    file=sys.stderr
                )
                width = 79

        TextWrapper.__init__(self,
                             width=width,
                             subsequent_indent=subsequent_indent)

    def fill(self, msg):
        wrapped = [TextWrapper.fill(self, line) for line in msg.split('\n')]
        return '\n'.join(wrapped)

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

def all_pred(func: Callable[[Any], bool], iterable: Iterable[Any]) -> bool:
    """
    Similar to the built-in `all()` function, this function ensures that
    `func()` returns `True` for every element of the supplied iterable.
    It short-circuits on the first failure.

    :param func:     function or lambda to call with each element
    :param iterable: the iterable

    :return: `True` if all elements pass, `False` otherwise
    """
    for i in iterable:
        if not func(i):
            return False

    return True

