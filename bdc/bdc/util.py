'''
Utility functions and classes
'''

from abc import ABCMeta

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

class DefaultStrMixin:
    '''
    Provides default implementations of __str__() and __repr__(). These
    implementations assume that all arguments passed to the constructor are
    captured in same-named fields in "self".
    '''
    __metaclass__ = ABCMeta

    def __str__(self):
        fields = []
        for field, value in self.__dict__.items():
            v = '"{0}"'.format(value) if isinstance(value, str) else value
            fields.append('{0}={1}'.format(field, v))
        return '{0}({1})'.format(self.__class__.__name__, ', '.join(fields))

    def __repr__(self):
        return self.__str__()
