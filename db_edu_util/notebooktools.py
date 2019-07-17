"""
Library of functions useful for parsing, testing, and generating Databricks
notebooks. Currently, this library is only used by gendbc. If we convert other
tools to use it, this module can be moved into its own separately installable
package.
"""
from __future__ import annotations # PEP 563 (allows annotation forward refs)

from collections import namedtuple
import codecs
import re
import os
import uuid
from enum import Enum
import json
from db_edu_util import debug, debug_is_enabled, set_debug
import dataclasses
from dataclasses import dataclass
from typing import Callable, Sequence, Pattern, Generator, Optional, Any, Dict

__all__ = ('NotebookError', 'NotebookParseError', 'NotebookLanguage',
           'CellType', 'NotebookCell', 'Notebook', 'parse_source_notebook')

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class NotebookError(Exception):
    """
    Base exception class for all notebook exceptions. Instances of this class
    can also be thrown.
    """
    def __init__(self, msg: str):
        Exception.__init__(self, msg)


class NotebookParseError(NotebookError):
    """
    Thrown to indicate that a notebook could not be parsed.
    """
    def __init__(self, msg: str):
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

    def for_json(self) -> str:
        '''
        Get the notebook language as it should be rendered in JSON.

        :returns: the language
        '''
        if self == NotebookLanguage.PYTHON:
            return 'python'
        return self.value

    @classmethod
    def from_path(cls, path: str) -> NotebookLanguage:
        """
        Return the appropriate language for a file, based on the extension.

        :param path: the path to the file
        :return: the notebook language
        :raises NotebookError: unknown extension
        """
        _, ext = os.path.splitext(path)
        return cls.from_extension(ext)

    @classmethod
    def from_extension(cls, ext: str) -> NotebookLanguage:
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
    def from_language(cls, language: NotebookLanguage) -> CellType:
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
        raise NotebookError(f'(BUG): Unknown {language}')

    @classmethod
    def from_string(cls, s: str) -> CellType:
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
            raise NotebookError(f'Unknown cell type: "{s}"')


@dataclass(frozen=True)
class NotebookCell:
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
    command: str
    position: int
    cell_type: CellType
    marked_magic: bool
    # Note: Can't just use uuid.uuid4() as the default, because it'd be
    # evaluated as class-definition time, meaning every cell would get the
    # same default value.
    guid: Optional[uuid.UUID] = dataclasses.field(default_factory=uuid.uuid4)

    def to_json_dict(self) -> Dict[str, Any]:
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


# An empty cell, used as a sentinel marker.
EmptyCell = NotebookCell(command='', position=0,
                         cell_type=CellType.UNKNOWN, marked_magic=True)


@dataclass(frozen=True)
class Notebook:
    """
    Parsed representation of a Databricks source notebook. Does not contain
    fields that appear in JSON notebooks but not source notebooks.
    """
    cells: Sequence[NotebookCell]
    path: str
    guid: Optional[uuid.UUID] = dataclasses.field(default_factory=uuid.uuid4)

    @property
    def name(self) -> str:
        """The name of the notebook (derived from the path)."""
        name, _ = os.path.splitext(os.path.basename(self.path))
        return name

    @property
    def language(self) -> NotebookLanguage:
        """The notebook language, derived from the path."""
        return NotebookLanguage.from_path(self.path)

    @classmethod
    def is_source_notebook(cls, path: str, encoding: str) -> bool:
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


    def to_source(self) -> Generator[None, str, None]:
        """
        Converts the parsed notebook to a source notebook.

        :return: a generator of the strings representing the lines of the
                 source notebook
        """
        comment_string = COMMENT_STRINGS[self.language]
        yield f'{comment_string} Databricks notebook source'
        for i, cell in enumerate(self.cells):
            if i > 0:
                yield ''
                yield f'{comment_string} COMMAND ----------'
                yield ''

            lines = cell.command.split('\n')
            if len(lines) == 0:
                continue

            magic = (len(lines[0]) > 0) and (lines[0][0] == '%')
            for line in lines:
                if magic:
                    yield f'{comment_string} MAGIC {line}'
                else:
                    yield line


    def to_json(self) -> str:
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
                'guid':            str(self.guid),
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

def _read_notebook(path: str, encoding: str) -> Sequence[str]:
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


def _leading_comment_pattern(comment_string: str) -> str:
    """
    Convert the comment string for a language into a (string) regular expression
    pattern that will match the comment at the beginning of a source notebook
    line.

    :param comment_string: the comment string

    :return: the pattern
    """
    return r'^\s*{}'.format(comment_string)


def _notebook_header_re(comment_string: str) -> Pattern:
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


def _parse_source_notebook(path: str, encoding: str) -> Notebook:
    """
    Parse a Databricks source notebook into a Notebook object.

    :param path:     the path to the notebook
    :param encoding: the encoding to use when reading the file

    :returns: a parsed Notebook object

    :raises NotebookParseError: if the notebook cannot be parsed
    :raises NotebookError:      other errors (e.g., invalid file type)
    """
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
                f'File "{path}" is missing expected Databricks header'
            )

    cells = []
    cur_cell = EmptyCell
    command_buf = []

    lines = _read_notebook(path, encoding)
    if len(lines) == 0:
        raise NotebookParseError(f'File "{path}" is empty.')

    saw_new_cell = False
    check_for_header(lines[0])
    saw_new_cell = True
    skip_next = False
    for i, line in enumerate(lines[1:]):
        line_num = i + 2 # account for skipped header

        if skip_next:
            debug(f'"{path}", line {line_num}: Skipping...')
            skip_next = False
            continue

        # If this line matches the start of a new cell marker, save the
        # existing cell and reset all the variables.
        if new_cell.search(line):
            debug(f'"{path}", line {line_num}: New command')
            if cur_cell != EmptyCell:
                # The last line of any cell should be blank and should
                # be removed, as it is really just a separator before the
                # marker starting a new cell.
                if len(command_buf[-1].strip()) == 0:
                    command_buf = command_buf[:-1]
                cells.append(
                    dataclasses.replace(cur_cell, command='\n'.join(command_buf))
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
            line = f'{m.group(1)}{m.group(2)}'

        # If we didn't see the new cell marker, then keep accumulating the
        # current cell and move on to the next line.
        if not saw_new_cell:
            debug(f'"{path}", line {line_num}: Not first line')
            command_buf.append(line)
            continue

        # Start of a new cell requires additional processing.
        saw_new_cell = False

        if not m:
            # Not a magic line. It is, therefore, a code cell of the same
            # type as the base language of the notebook.
            debug(f'{path}, line {line_num}: No magic')
            command_buf.append(line)
            cur_cell = dataclasses.replace(
                cur_cell,
                cell_type=CellType.from_language(language),
                marked_magic=False
            )
            continue

        # Magic line as first line in cell. If it's an empty magic line, skip it.
        token = m.group(1).strip()
        if not token:
            debug(f'"{path}", line {line_num}: Skipping empty magic.')
            continue

        # Extract cell type, if it exists.
        debug(f'"{path}", line {line_num}: Magic')
        if (not token) or (token[0] != '%'):
            raise NotebookParseError(
                f'"{path}", line {line_num}: Bad first magic cell line: {line}'
            )

        command_buf.append(line)
        cur_cell = dataclasses.replace(
            cur_cell, cell_type=CellType.from_string(token),
        )

    # If there's an unfinished cell left, finish it.
    if cur_cell != EmptyCell:
        cells.append(
            dataclasses.replace(cur_cell, command='\n'.join(command_buf))
        )

    cells = [dataclasses.replace(cell, position=i + 1, guid=uuid.uuid4())
             for i, cell in enumerate(cells)]
    return Notebook(cells=cells, path=path)

# -----------------------------------------------------------------------------
# Public Functions
# -----------------------------------------------------------------------------

def parse_source_notebook(path: str,
                          encoding: str,
                          debugging: bool = False) -> Notebook:
    """
    Parse a Databricks source notebook into a Notebook object.

    :param path:      the path to the notebook
    :param encoding:  the encoding to use when reading the file
    :param debugging: True to enable debug messages, False otherwise

    :returns: a parsed Notebook object

    :raises NotebookParseError: if the notebook cannot be parsed
    :raises NotebookError:      other errors (e.g., invalid file type)
    """
    prev_debug = debug_is_enabled()
    try:
        set_debug(debugging)
        return _parse_source_notebook(path, encoding)
    finally:
        set_debug(prev_debug)
