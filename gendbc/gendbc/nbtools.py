"""
Library of functions useful for parsing, testing, and generating Databricks
notebooks. Currently, this library is only used by gendbc. If we convert other
tools to use it, this module can be moved into its own separately installable
package.
"""
from collections import namedtuple
import codecs
import re
import os
import uuid
from enum import Enum
from typing import Callable, Sequence, Pattern, Generator
import json
from abc import abstractmethod

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class NotebookError(Exception):
    """
    Base exception class for all notebook exceptions. Instances of this class
    can also be thrown.
    """
    def __init__(self,
                 msg # type: str
                 ):
        Exception.__init__(self, msg)


class NotebookParseError(NotebookError):
    """
    Thrown to indicate that a notebook could not be parsed.
    """
    def __init__(self,
                 msg # type: str
                ):
        Exception.__init__(self, msg)


class NotebookLanguage(Enum):
    """
    An enumeration of the languages supported by notebooks, including some
    utility (class-level) functions.
    """
    SCALA      = 'scala'
    R          = 'r'
    PYTHON     = 'py'
    SQL        = 'sql'

    def for_json(self):
        # type: () -> str
        '''
        Get the notebook language as it should be rendered in JSON.

        :returns: the language
        '''
        if self == NotebookLanguage.PYTHON:
            return 'python'
        return self.value

    @classmethod
    def from_path(cls, path):
        # type: (str) -> NotebookLanguage
        """
        Return the appropriate language for a file, based on the extension.

        :param path: the path to the file
        :return: the notebook language
        :raises NotebookError: unknown extension
        """
        _, ext = os.path.splitext(path)
        return cls.from_extension(ext)

    @classmethod
    def from_extension(cls,
                       ext # type: str
                       ):
        # type: (str) -> NotebookLanguage
        """
        Return the appropriate language for a file extension.

        :param ext: the extension
        :return: the notebook language
        :raises NotebookError: unknown extension
        """
        ext = ext.lower()
        values = { ('.' + k.value): k for k in cls }
        values['.python'] = NotebookLanguage.PYTHON
        try:
            return values[ext]
        except KeyError:
            raise NotebookError('Unknown extension: "{}"'.format(ext))


class CellType(Enum):
    """
    Enumeration of the valid cell types.
    """
    MD         = 'md'
    MD_SANDBOX = 'md-sandbox'
    SCALA      = 'scala'
    R          = 'r'
    PYTHON     = 'python'
    SQL        = 'sql'
    SH         = 'sh'
    FS         = 'fs'
    RUN        = 'run'
    TIMEIT     = 'timeit'
    UNKNOWN    = '?'

    @classmethod
    def from_language(cls, language):
        # type: (NotebookLanguage) -> CellType
        """
        Return the appropriate cell type for a code cell of a given language.

        :param language: the NotebookLanguage
        :return: the CellType value
        :raises NotebookError: unknown language
        """
        if language == NotebookLanguage.SCALA:
            return CellType.SCALA
        if language == NotebookLanguage.PYTHON:
            return CellType.PYTHON
        if language == NotebookLanguage.R:
            return CellType.R
        if language == NotebookLanguage.SQL:
            return CellType.SQL
        raise NotebookError('(BUG): {} passed to CellType.from_language'.format(
            language
        ))

    @classmethod
    def from_string(cls, s):
        # type: (str) -> CellType
        """
        Return the appropriate cell type for a string.

        :param language: the NotebookLanguage
        :return: the CellType value
        :raises NotebookError: unknown string
        """
        s = s.lower()
        values = { k.value: k for k in CellType }
        s = s[1:] if s[0] == '%' else s
        try:
            return values[s]
        except KeyError:
            raise NotebookError('Unknown cell type: "{}"'.format(s))

_NotebookCell = namedtuple('NotebookCell', ('command', 'guid', 'position',
                                            'cell_type', 'marked_magic'))
# Create a wrapper class around _NotebookCell, so we can docstring it.
# In Python 2 (unlike Python 3), you can't write to __doc__. This solution
# just wraps the namedtuple in a thin shell. Use of __slots__ means we retain
# the lightweight nature. See https://stackoverflow.com/a/1606478/53495
class NotebookCell(_NotebookCell):
    """
    Represents a parsed notebook cell. This class is just a thin wrapper around
    a namedtuple. It contains the following fields:

    command (str):        the contents of the cell
    guid (UUID):          a unique identifier for the cell
    position (int):       the 1-based ordinal position of the cell
    cell_type (CellType): the cell type
    marked_magic (bool):  True of the cell was explicitly marked with a magic
                          string. False means it's implicitly a code cell of
                          the base notebook language.
    """

    __slots__ = ()

    def to_json_dict(self):
        # type: () -> dict
        """
        Convert the parsed notebook cell into a dict containing all the fields
        necessary to represent the cell in a Databricks JSON-formatted
        notebook.

        :return: a JSON-ready dict.
        """
        return {
            'bindings':                     {},
            'collapsed':                    False,
            'command':                      self.command,
            'commandTitle':                 '',
            'commandType':                  'auto',
            'commandVersion':               0,
            'commentThread':                [],
            'commentsVisible':              False,
            'customPlotOptions':            {},
            'datasetPreviewNameToCmdIdMap': {},
            'diffDeletes':                  [],
            'diffInserts':                  [],
            'displayType':                  'table',
            'error':                        None,
            'errorSummary':                 None,
            'finishTime':                   0,
            'globalVars':                   {},
            'guid':                         str(self.guid),
            'height':                       'auto',
            'hideCommandCode':              False,
            'hideCommandResult':            False,
            'iPythonMetadata':              None,
            'inputWidgets':                 {},
            'latestUser':                   '',
            'latestUserId':                 None,
            'nuid':                         str(uuid.uuid4()),
            'origId':                       0,
            'parentHierarchy':              [],
            'pivotAggregation':             None,
            'pivotColumns':                 None,
            'position':                     self.position,
            'results':                      None,
            'showCommandTitle':             False,
            'startTime':                    0,
            'state':                        'finished',
            'streamStates':                 {},
            'submitTime':                   0,
            'subtype':                      'command',
            'version':                      'CommandV1',
            'width':                        'auto',
            'workflows':                    [],
            'xColumns':                     None,
            'yColumns':                     None,
        }

    def __repr__(self):
        return _NotebookCell.__repr__(self).replace(
            '_NotebookCell', 'NotebookCell'
        )

    def __str__(self):
        return _NotebookCell.__str__(self).replace(
            '_NotebookCell', 'NotebookCell'
        )

# An empty cell, used as a sentinel marker.
EmptyCell = NotebookCell(command='', guid=None, position=0,
                         cell_type=CellType.UNKNOWN, marked_magic=True)

class Copyable(object):
    '''
    Mixin for a class, providing a _replace() method that is consistent with
    the _replace() method you automatically get with a namedtuple. Because of
    the way this class instantiates the subclass, Copyable cannot use a
    metaclass of ABCMeta. Pretend this class is abstract.
    '''

    @abstractmethod
    def __init__(self):
        pass

    def _replace(self, **kw):
        '''
        Create a new instance of the object on which _replace() is called,
        replacing only those fields specified as keyword parameters and copying
        the rest. The original object is unmodified.

        :param kw: the key=value parameters for the fields to replace.
        :return: a copy of this object, with the specified fields replaced
        :raises KeyError: if a nonexistent field is specified
        '''
        fields = self._public_fields()
        arg_keys = set(kw.keys())
        unknown = arg_keys - fields
        if unknown:
            raise KeyError('Unknown fields passed to copy(): {}'.format(
                ', '.join(unknown)
            ))

        args = kw
        for field in fields:
            if field in args:
                continue
            args[field] = eval('self.{}'.format(field))

        return self.__class__(**args)

    def _public_fields(self):
        return {f for f in self.__dict__.keys() if f[0] != '_'} | self._props()

    def _props(self):
        cls = self.__class__
        return set([p for p in dir(cls) if isinstance(getattr(cls, p),property)])


class Notebook(Copyable):
    """
    Parsed representation of a Databricks source notebook. Does not contain
    fields that appear in JSON notebooks but not source notebooks.
    """

    def __init__(self,
                 cells,    # type: Sequence[NotebookCell]
                 path      # type: str
                 ):
        """
        :param cells: the parsed notebook cells
        :param path:  the path to the source notebook that was parsed
        """

        name, _ = os.path.splitext(os.path.basename(path))

        self._name     = name
        self._guid     = uuid.uuid4()
        self._cells    = cells
        self._language = NotebookLanguage.from_path(path)
        self._path     = path

    @property
    def name(self):
        # type: () -> str
        """
        :return: the name of the notebook (derived from the path)
        """
        return self._name

    @property
    def path(self):
        # type: () -> str
        """
        :return: the path to the source notebook that was parsed
        """
        return self._path

    @property
    def guid(self):
        # type: () -> UUID
        """
        :return: a unique identifier for the notebook
        """
        return self._guid

    @property
    def cells(self):
        # type: () -> Sequence[NotebookCell]
        """
        :return: the parsed notebook cells
        """
        return self._cells

    @property
    def language(self):
        # type: () -> NotebookLanguage
        """
        :return: the base programming language of the notebook, as derived
                 from the extension
        """
        return self._language

    def __str__(self):
        return ('Notebook(name="{}", guid="{}", path="{}", language={}, ' +
                'len(cells)={})').format(
            self.name, self.guid, self.path, self.language, len(self.cells)
        )

    def __repr__(self):
        return self.__str__()

    @classmethod
    def is_source_notebook(cls, path, encoding):
        # type: (str, str) -> bool
        """
        Determine whether a file is a source notebook. This function first
        checks the file extension. If the extension is one of the valid source
        notebook extensions, the function then determines whether the file
        starts with the Databricks notebook header line.

        :param path:     the path to the file to check
        :param encoding: the encoding to use when opening the file

        :return: True if the notebook is a Databricks source notebook, False
                 otherwise
        """
        valid_extensions = {'.scala', '.r', '.py', '.sql'}

        _, ext = os.path.splitext(path)
        if ext.lower() not in valid_extensions:
            return False

        lines = _read_notebook(path, encoding)
        if len(lines) == 0:
            return False

        language = NotebookLanguage.from_path(path)
        comment_string = COMMENT_STRINGS[language]
        header_re = _notebook_header_re(comment_string)
        if not header_re.search(lines[0]):
            return False

        return True


    def to_source(self):
        # type: () -> Generator[str]
        """
        Converts the parsed notebook to a source notebook.

        :return: a generator of the strings representing the lines of the
                 source notebook
        """
        comment_string = COMMENT_STRINGS[self.language]
        yield '{} Databricks notebook source'.format(comment_string)
        for i, cell in enumerate(self.cells):
            if i > 0:
                yield ''
                yield '{} COMMAND ----------'.format(comment_string)
                yield ''

            lines = cell.command.split('\n')
            if len(lines) == 0:
                continue

            magic = (len(lines[0]) > 0) and (lines[0][0] == '%')
            for line in lines:
                if magic:
                    yield '{} MAGIC {}'.format(comment_string, line)
                else:
                    yield line


    def to_json(self):
        # type: () -> str
        """
        Converts the parsed notebook to JSON, suitable for stuffing into a DBC.

        :return: the JSON string representing the notebook.
        """
        cell_hashes = [cell.to_json_dict() for cell in self.cells]
        return json.dumps(
            {
                'commands':        cell_hashes,
                'dashboards':      [],
                'globalVars':      {},
                'guid':            str(self._guid),
                'iPythonMetadata': None,
                'inputWidgets':    {},
                'language':        self.language.for_json(),
                'name':            self.name,
                'origId':          0,
                'version':         'NotebookV1',
            }
        )

# -----------------------------------------------------------------------------
# Constants based on the above
# -----------------------------------------------------------------------------

COMMENT_STRINGS = {
    NotebookLanguage.SCALA:  '//',
    NotebookLanguage.R:      '#',
    NotebookLanguage.PYTHON: '#',
    NotebookLanguage.SQL:    '--',
}

# -----------------------------------------------------------------------------
# Internal Functions
# -----------------------------------------------------------------------------

def _read_notebook(path, encoding):
    # type: (str, str) -> Sequence[str]
    """
    Read a source notebook into a list of lines, removing trailing newlines.

    :param path:      the path to the source notebook
    :param encoding:  the encoding to use to read the notebook

    :return: the list of lines
    """
    buf = []
    with codecs.open(path, mode='r', encoding=encoding) as f:
        for line in f.readlines():
            # Don't use rstrip(), because we want to keep any trailing white
            # space, except for the trailing newline.
            if len(line) == 0:
                buf.append(line)
                continue
            if line[-1] != '\n':
                buf.append(line)
                continue
            buf.append(line[:-1])

    return buf

def _leading_comment_pattern(comment_string):
    # type: (str) -> str
    """
    Convert the comment string for a language into a (string) regular expression
    pattern that will match the comment at the beginning of a source notebook
    line.

    :param comment_string: the comment string

    :return: the pattern
    """
    return r'^\s*{}'.format(comment_string)


def _notebook_header_re(comment_string):
    # type: (str) -> Pattern
    """
    Given a language comment string, return a compiled regular expression that
    will match the Databricks notebook header line.

    :param comment_string: the language comment string

    :return: the parsed regular expression
    """
    return re.compile(
        r'{}\s+Databricks\s+notebook.*$'.format(
            _leading_comment_pattern(comment_string)
        )
    )


# -----------------------------------------------------------------------------
# Public Functions
# -----------------------------------------------------------------------------

def parse_source_notebook(path,     # type: str
                          encoding, # type: str
                          debug     # type: Callable
                         ):
    # type: (...) -> Notebook
    """
    Parse a Databricks source notebook into a Notebook object.

    :param path:     the path to the notebook
    :param encoding: the encoding to use when reading the file
    :param debug:    True to enable debug messages, False otherwise

    :returns: a parsed Notebook object

    :raises NotebookParseError: if the notebook cannot be parsed
    :raises NotebookError:      other errors (e.g., invalid file type)
    """
    def emit_debug(msg):
        if debug:
            debug(msg)

    language = NotebookLanguage.from_path(path)
    comment_string = COMMENT_STRINGS[language]

    leading_comment = _leading_comment_pattern(comment_string)
    header = _notebook_header_re(comment_string)
    magic = re.compile(
        r'{}\s+MAGIC\s?([^\s]*)(.*)$'.format(leading_comment)
    )
    new_cell = re.compile(
        r'{}\s+COMMAND\s+-+.*$'.format(leading_comment)
    )

    def check_for_header(line):
        if not header.search(line):
            raise NotebookParseError(
                'File "{}" is missing expected Databricks header'.format(
                    path
                )
            )

    c = Copyable()
    cells = []
    cur_cell = EmptyCell
    command_buf = []

    lines = _read_notebook(path, encoding)
    if len(lines) == 0:
        raise NotebookParseError('File "{}" is empty.'.format(path))

    saw_new_cell = False
    check_for_header(lines[0])
    saw_new_cell = True
    skip_next = False
    for i, line in enumerate(lines[1:]):
        line_num = i + 2 # account for skipped header

        if skip_next:
            emit_debug("Line {}: Skipping...".format(line_num))
            skip_next = False
            continue

        # If this line matches the start of a new cell marker, save the
        # existing cell and reset all the variables.
        if new_cell.search(line):
            emit_debug("Line {}: New command".format(line_num))
            if cur_cell != EmptyCell:
                # The last line of any cell should be blank and should
                # be removed, as it is really just a separator before the
                # marker starting a new cell.
                if len(command_buf[-1].strip()) == 0:
                    command_buf = command_buf[:-1]
                cells.append(
                    cur_cell._replace(command='\n'.join(command_buf))
                )
            cur_cell = EmptyCell
            saw_new_cell = True
            skip_next = True
            command_buf = []
            continue

        # Is this cell a "MAGIC" cell? If so, extract the contents without
        # the leading MAGIC indicator.
        m = magic.search(line)
        if m:
            line = u'{}{}'.format(m.group(1), m.group(2))

        # If we didn't see the new cell marker, then keep accumulating the
        # current cell and move on to the next line.
        if not saw_new_cell:
            emit_debug("Line {}: Not first line".format(line_num))
            command_buf.append(line)
            continue

        # Start of a new cell requires additional processing.
        emit_debug("Line {}: First line of new cell: <{}>".format(
            line_num, line
        ))
        saw_new_cell = False

        if not m:
            # Not a magic line. It is, therefore, a code cell of the same
            # type as the base language of the notebook.
            emit_debug("Line {}: No magic".format(line_num))
            command_buf.append(line)
            cur_cell = cur_cell._replace(
                cell_type=CellType.from_language(language),
                marked_magic=False
            )
            continue

        # Magic line as first cell. Extract cell type, if it exists.
        emit_debug("Line {}: Magic".format(line_num))
        token = m.group(1).strip()
        if (not token) or (token[0] != '%'):
            raise NotebookParseError(
                '''"{}", line {}: Bad first magic cell line: {}'''.format(
                    path, line_num, line
                )
            )

        command_buf.append(line)
        cur_cell = cur_cell._replace(
            cell_type=CellType.from_string(token),
        )

    # If there's an unfinished cell left, finish it.
    if cur_cell != EmptyCell:
        cells.append(
            cur_cell._replace(command='\n'.join(command_buf))
        )

    cells = [cell._replace(position=i + 1, guid=uuid.uuid4())
             for i, cell in enumerate(cells)]
    return Notebook(cells=cells, path=path)



