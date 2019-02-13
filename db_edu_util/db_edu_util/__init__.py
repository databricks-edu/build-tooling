"""
Utility library used by build tools.
"""

VERSION = '1.1.0'

from typing import Callable, Iterable, Any

__all__ = ['all_pred', 'notebooktools', 'db_cli']


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

