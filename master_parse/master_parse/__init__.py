#!/usr/bin/env python
"""
master_parse.py: convert master Databricks notebooks to other formats

Converts notebooks exported in "source" format from Databricks
into separate notebooks by language and for instructor and student use.
It can also generate IPython notebooks.

Works with Python 2 and Python 3. When using IPython, IPython version 3 is
required.

This module can be used as a command or a library. To see the valid command
line arguments, run with no arguments. If used as a library, the main
entry point is process_notebooks().
"""

from __future__ import print_function

import glob
import os
import os.path
import re
import codecs
from enum import Enum
from collections import namedtuple
from string import Template
from InlineToken import InlineToken, expand_inline_tokens
from datetime import datetime

VERSION = "1.11.1"

# -----------------------------------------------------------------------------
# Enums. (Implemented as classes, rather than using the Enum functional
# API, for ease of modification.)
# -----------------------------------------------------------------------------

class CommandLabel(Enum):
    IPYTHON_ONLY      = 'IPYTHON_ONLY'
    PYTHON_ONLY       = 'PYTHON_ONLY'
    SCALA_ONLY        = 'SCALA_ONLY'
    R_ONLY            = 'R_ONLY'
    SQL_ONLY          = 'SQL_ONLY'
    ANSWER            = 'ANSWER'
    TODO              = 'TODO'
    TEST              = 'TEST'
    PRIVATE_TEST      = 'PRIVATE_TEST'
    DATABRICKS_ONLY   = 'DATABRICKS_ONLY'
    INLINE            = 'INLINE'
    ALL_NOTEBOOKS     = 'ALL_NOTEBOOKS'
    INSTRUCTOR_NOTE   = 'INSTRUCTOR_NOTE'
    VIDEO             = 'VIDEO'

class CommandCode(Enum):
    SCALA             = 'scala'
    PYTHON            = 'python'
    R                 = 'r'
    SQL               = 'sql'
    MARKDOWN          = 'md'
    MARKDOWN_SANDBOX  = 'md-sandbox'
    FILESYSTEM        = 'filesystem'
    SHELL             = 'shell'
    RUN               = 'run'
    FS                = 'fs'
    SH                = 'sh'

    def is_markdown(self):
        return self.name in ['MARKDOWN', 'MARKDOWN_SANDBOX']

    def on_separate_line(self):
        return self.name in ['MARKDOWN', 'MARKDOWN_SANDBOX', 'SQL', 'SCALA',
                             'PYTHON', 'R']

class NotebookKind(Enum):
    DATABRICKS = 'Databricks'
    IPYTHON    = 'IPython'

class NotebookUser(Enum):
    INSTRUCTOR = 'INSTRUCTOR'
    EXERCISES  = 'EXERCISES'
    ANSWERS    = 'ANSWERS'

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value.lower()

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

def _s3_icon_url(image):
    return (
        'https://s3-us-west-2.amazonaws.com/curriculum-release/images/eLearning/' +
        image
    )

INLINE_TOKENS = [
    InlineToken(
        title='Hint',
        tag=':HINT:',
        image=_s3_icon_url('icon-light-bulb.svg'),
        template=r'<img alt="${title}" title="${title}" style="${style}" src="${image}"/>&nbsp;**${title}:**',
        style='height:1.75em; top:0.3em'
    ),
    InlineToken(
        title='Caution',
        tag=':CAUTION:',
        image=_s3_icon_url('icon-warning.svg'),
        style='height:1.3em; top:0.0em'
    ),
    InlineToken(
        tag=':BESTPRACTICE:',
        title='Best Practice',
        image=_s3_icon_url('icon-blue-ribbon.svg'),
        style='height:1.75em; top:0.3em'
    ),
    #InlineToken(
    #    tag=':KEYPOINT:',
    #    title='Key Point',
    #    image=_s3_icon_url('icon-key.svg'),
    #    style='height:1.3em; top:0.1.5em'
    #),
    InlineToken(
        tag=':SIDENOTE:',
        title='Side Note',
        image=_s3_icon_url('icon-note.webp'),
        style='height:1.75em; top:0.05em; transform:rotate(15deg)'
    ),
]

DEFAULT_TEST_CELL_ANNOTATION = "Run this cell to test your solution."

ALL_CELL_TYPES = { c for c in CommandCode }
CODE_CELL_TYPES = {
    CommandCode.SCALA,
    CommandCode.SQL,
    CommandCode.R,
    CommandCode.PYTHON
}

VALID_CELL_TYPES_FOR_LABELS = {
    CommandLabel.IPYTHON_ONLY:    CODE_CELL_TYPES | {CommandCode.MARKDOWN,
                                                     CommandCode.MARKDOWN_SANDBOX},
    CommandLabel.DATABRICKS_ONLY: ALL_CELL_TYPES,
    CommandLabel.PYTHON_ONLY:     ALL_CELL_TYPES,
    CommandLabel.SCALA_ONLY:      ALL_CELL_TYPES,
    CommandLabel.R_ONLY:          ALL_CELL_TYPES,
    CommandLabel.SQL_ONLY:        ALL_CELL_TYPES,
    CommandLabel.ANSWER:          CODE_CELL_TYPES,
    CommandLabel.TODO:            CODE_CELL_TYPES,
    CommandLabel.TEST:            CODE_CELL_TYPES,
    CommandLabel.PRIVATE_TEST:    CODE_CELL_TYPES,
    CommandLabel.INLINE:          ALL_CELL_TYPES,
    CommandLabel.INSTRUCTOR_NOTE: { CommandCode.MARKDOWN,
                                    CommandCode.MARKDOWN_SANDBOX },
    CommandLabel.ALL_NOTEBOOKS:   ALL_CELL_TYPES,
    CommandLabel.VIDEO:           { CommandCode.MARKDOWN,
                                    CommandCode.MARKDOWN_SANDBOX },
}

# Ensure that all labels are captured in VALID_CELL_TYPES_FOR_LABELS
assert set(VALID_CELL_TYPES_FOR_LABELS.keys()) == {i for i in CommandLabel}

DEPRECATED_LABELS = {
    CommandLabel.INLINE,
    CommandLabel.IPYTHON_ONLY,
    CommandLabel.DATABRICKS_ONLY
}

DEFAULT_ENCODING_IN = 'utf-8'
DEFAULT_ENCODING_OUT = 'utf-8'
DEFAULT_OUTPUT_DIR = 'build_mp'

# VIDEO_TEMPLATE (a string template) requires ${id} and ${title}. ${title}
# is currently ignored.
VIDEO_TEMPLATE = (
'''<script src="https://fast.wistia.com/embed/medias/${id}.jsonp" async></script>
<script src="https://s3-us-west-2.amazonaws.com/files.training.databricks.com/courses/spark-sql/Wistia.js" async></script>
<div class="wistia_embed wistia_async_${id}" style="height:360px;width:640px;color:red">
  Error displaying video. Please click the link, below.
</div>
<a target="_blank" href="https://fast.wistia.net/embed/iframe/${id}?seo=false">
<img style="width:16px" alt="Opens in new tab" src="''' + _s3_icon_url('external-link-icon.png') +
'''"/>&nbsp;Watch full-screen.</a>
''')

INSTRUCTOR_NOTE_HEADING = '<h2 style="color:red">Instructor Note</h2>'

DEFAULT_NOTEBOOK_HEADING = """<div style="text-align: center; line-height: 0; padding-top: 9px;">
  <img src="https://cdn2.hubspot.net/hubfs/438089/docs/training/dblearning-banner.png" alt="Databricks Learning" width="555" height="64">
</div>"""

# {0} is replaced with the copyright year.
DEFAULT_NOTEBOOK_FOOTER = """&copy; {0} Databricks, Inc. All rights reserved.
Apache, Apache Spark, Spark and the Spark logo are trademarks of the <a href="http://www.apache.org/">Apache Software Foundation</a>.<br><br><a href="https://databricks.com/privacy-policy">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use">Terms of Use</a>"""

CC_LICENSE = """<div>
<a rel="license" href="http://creativecommons.org/licenses/by-nc-nd/4.0/">
  <img alt="Creative Commons License" style="border-width:0"
       src="https://i.creativecommons.org/l/by-nc-nd/4.0/88x31.png"/>
</a>
<br/>
This work is licensed under a
<a rel="license" href="http://creativecommons.org/licenses/by-nc-nd/4.0/">
  Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International
  License.
</a>
</div>"""

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class Params(object):
    '''
    Parsed command-line parameters or manually constructed parameters,
    passed to process_notebooks().
    '''
    def __init__(self,
                 path=None,
                 output_dir=DEFAULT_OUTPUT_DIR,
                 databricks=True,
                 ipython=False,
                 scala=False,
                 python=False,
                 r=False,
                 sql=False,
                 instructor=False,
                 answers=False,
                 exercises=False,
                 creative_commons=False,
                 add_footer=False,
                 notebook_footer_path=None,
                 add_heading=False,
                 notebook_heading_path=None,
                 encoding_in=DEFAULT_ENCODING_IN,
                 encoding_out=DEFAULT_ENCODING_OUT,
                 enable_verbosity=False,
                 enable_debug=False,
                 copyright_year=None):
        self.path = path
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.databricks = databricks
        self.ipython = ipython
        self.scala = scala
        self.python = python
        self.r = r
        self.sql = sql
        self.instructor = instructor
        self.answers = answers
        self.exercises = exercises
        self.creative_commons = creative_commons
        self.add_heading = add_heading
        self.add_footer = add_footer
        self.encoding_in = encoding_in or DEFAULT_ENCODING_IN
        self.encoding_out = encoding_out or DEFAULT_ENCODING_OUT
        self.enable_verbosity = enable_verbosity
        self.enable_debug = enable_debug
        self.notebook_heading_path = notebook_heading_path
        self._notebook_heading = None
        self._notebook_footer = None
        self.notebook_footer_path = notebook_footer_path
        self.copyright_year = copyright_year or datetime.now().year

        for purpose, file in (('Notebook footer', notebook_footer_path),
                              ('Notebook header', notebook_heading_path)):
            if file is not None:
                self._check_path(file, purpose)

    @property
    def notebook_footer(self):
        if self._notebook_footer is None:
            if self.notebook_footer_path is None:
                self._notebook_footer = DEFAULT_NOTEBOOK_FOOTER.format(
                    self.copyright_year
                )
            else:
                self._notebook_footer= ''.join(
                    open(self.notebook_footer_path).readlines()
                )
        return self._notebook_footer

    @property
    def notebook_heading(self):
        if self._notebook_heading is None:
            if self.notebook_heading_path is None:
                self._notebook_heading = DEFAULT_NOTEBOOK_HEADING
            else:
                self._notebook_heading = ''.join(
                    open(self.notebook_heading_path).readlines()
                )
        return self._notebook_heading

    @classmethod
    def _check_path(cls, file, purpose):
        if not os.path.exists(file):
            raise IOError('{0} "{1}" does not exist.'.format(purpose, file))
        if not os.path.isfile(file):
            raise IOError('{0} "{1}" is not a file.'.format(purpose, file))

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return 'Params({0})'.format(
            ','.join([
                '{0}={1}'.format(f, self.__getattribute__(f))
                for f in self.__dict__
            ])
        )


Command = namedtuple('Command', ['part', 'code', 'labels', 'content'])


class NotebookGenerator(object):
    code_to_output_dir = {CommandCode.SQL:    'sql',
                          CommandCode.SCALA:  'scala',
                          CommandCode.PYTHON: 'python',
                          CommandCode.R:      'r'}

    param_to_label = {
        CommandCode.PYTHON: {CommandLabel.PYTHON_ONLY},
        CommandCode.SCALA: {CommandLabel.SCALA_ONLY},
        CommandCode.SQL: {CommandLabel.SQL_ONLY},
        CommandCode.R: {CommandLabel.R_ONLY},
        CommandCode.FS: {CommandLabel.ALL_NOTEBOOKS},
        CommandCode.SH: {CommandLabel.ALL_NOTEBOOKS},
        NotebookKind.DATABRICKS: {CommandLabel.DATABRICKS_ONLY},
        NotebookKind.IPYTHON: {CommandLabel.IPYTHON_ONLY},
        NotebookUser.ANSWERS: {CommandLabel.ANSWER,
                              CommandLabel.PRIVATE_TEST},
        NotebookUser.INSTRUCTOR: {CommandLabel.ANSWER,
                                  CommandLabel.INSTRUCTOR_NOTE,
                                  CommandLabel.PRIVATE_TEST},
        NotebookUser.EXERCISES: {CommandLabel.TODO},
    }

    user_to_extension = {
        NotebookUser.INSTRUCTOR: '_instructor',
        NotebookUser.EXERCISES: '_exercises',
        NotebookUser.ANSWERS: '_answers'
    }

    def __init__(self, notebook_kind, notebook_user, notebook_code, params):
        '''

        :param notebook_kind:  the NotebookKind
        :param notebook_user:  the NotebookUser
        :param notebook_code:  the parsed notebook code
        :param params:         parsed (usually command-line) parameters
        '''
        base_keep = set(CommandLabel.__members__.values())
        self.keep_labels = self._get_labels(notebook_kind,
                                            notebook_user,
                                            notebook_code)
        # discard labels not explicitly kept
        self.discard_labels = base_keep - self.keep_labels
        self.remove = [_dbc_only, _scala_only, _python_only, _new_part, _inline,
                       _all_notebooks, _instructor_note, _video]
        self.replace = [(_ipythonReplaceRemoveLine, ''),
                        _rename_public_test,
                        _rename_import_public_test]
        self.notebook_kind = notebook_kind
        self.notebook_user = notebook_user
        self.notebook_code = notebook_code
        self.file_ext = self._get_extension()
        self.base_comment = _code_to_comment[self.notebook_code]
        self.params = params

    def _get_labels(self, *params):
        labels = {CommandLabel.TEST, CommandLabel.INLINE}
        for param in params:
            label = NotebookGenerator.param_to_label[param]
            labels.update(label)
        return labels

    def _get_extension(self):
        return (NotebookGenerator.user_to_extension[self.notebook_user] +
                Parser.code_to_extension[self.notebook_code])

    def _check_cell_type(self, command_code, labels, cell_num):
        for label in labels:
            valid_codes_for_label = VALID_CELL_TYPES_FOR_LABELS[label]
            if command_code not in valid_codes_for_label:
                magics = ['%{0}'.format(c.value) for c in valid_codes_for_label]
                raise Exception(
                    ("Cell #{0}: Found {1} in a {2} cell, but it's only valid " +
                     "in {3} cells.").format(
                        cell_num, label.value, command_code, ', '.join(magics)
                    )
                )

    def generate(self, header, commands, input_name, params, parts=True):

        _verbose('Generating {0} notebook(s) for "{1}"'.format(
            str(self.notebook_user), input_name
        ))

        is_IPython = self.notebook_kind == NotebookKind.IPYTHON
        is_instructor_nb = self.notebook_user == NotebookUser.INSTRUCTOR

        command_cell = _command_cell.format(self.base_comment)

        max_part = max([part for (part, _, _, _) in commands]) if parts else 0

        # Don't generate parts for IPython notebooks or instructor notebooks.
        if max_part == 0 or is_IPython or is_instructor_nb:
            parts = False

        # generate full notebook when generating parts
        if parts:
            self.generate(header, commands, input_name, params, parts=False)

        base_file, _ = os.path.splitext(os.path.basename(input_name))
        for i in range(max_part + 1): # parts are zero indexed

            part_base = '_part{0}'
            part_string = part_base.format(i + 1) if parts else ''

            out_dir = os.path.join(
                _output_dir, base_file,
                NotebookGenerator.code_to_output_dir[self.notebook_code]
            )

            if not os.path.exists(out_dir):
                os.makedirs(out_dir)

            file_out = os.path.join(out_dir,
                                    base_file + part_string + self.file_ext)
            if is_IPython:
                file_out = file_out.replace('.py', '.ipynb')

            magic_prefix = '{0} MAGIC'.format(self.base_comment)

            with codecs.open(file_out, 'w', _file_encoding_out,
                             errors=_file_encoding_errors) as output:

                # don't write the first # command --- for databricks
                is_first = not is_IPython

                if is_IPython:
                    header_adj = _header
                else:
                    # use proper comment char
                    header_adj = re.sub(_comment, self.base_comment, header)
                    sep = ""

                    # Optional heading.
                    if params.add_heading:
                        header_adj += '\n{0} %{1}\n{0} {2}'.format(
                            magic_prefix, CommandCode.MARKDOWN_SANDBOX.value,
                            params.notebook_heading
                        )
                        sep = '\n' + _command_cell.format(self.base_comment)
                        is_first = False

                    if params.creative_commons:
                        header_adj += sep
                        header_adj += '\n{0} %{1}\n{0} {2}'.format(
                            magic_prefix, CommandCode.MARKDOWN_SANDBOX.value,
                            CC_LICENSE
                        )
                        is_first = False

                output.write(header_adj + '\n')

                added_run = False
                for (cell_num, (part, code, labels, content)) in enumerate(commands):
                    cell_num += 1 # 1-based, for error reporting

                    self._check_cell_type(code, labels, cell_num)

                    if parts:
                        if part > i:  # don't show later parts
                            break
                        elif part == i - 1 and not added_run:
                            # add %run command before new part
                            exercises = NotebookGenerator.user_to_extension[
                                NotebookUser.EXERCISES
                            ]
                            answers = NotebookGenerator.user_to_extension[
                                NotebookUser.ANSWERS
                            ]

                            remove_ext = lambda path: os.path.splitext(path)[0]

                            # Convert the exercises file name into an answer
                            # file name.
                            answers_file = remove_ext(
                                file_out.replace(exercises, answers)
                            ).replace(
                                part_string, part_base.format(i)
                            )

                            # Databricks now supports relative %run paths.

                            runCommand = '{0} MAGIC %run {1}'.format(
                                self.base_comment, os.path.basename(answers_file)
                            )
                            is_first = self._write_command(
                                output, command_cell, [runCommand, ''], is_first
                            )
                            added_run = True
                            continue
                        elif part < i:  # earlier parts will be chained in %run
                            continue

                    if CommandLabel.INSTRUCTOR_NOTE in labels:
                        # Special case processing: Add instructor note heading,
                        # and force use of %md-sandbox

                        code = CommandCode.MARKDOWN_SANDBOX
                        content = (
                            [INSTRUCTOR_NOTE_HEADING] +
                            content
                        )

                    # Expand inline callouts.
                    (content, sandbox) = expand_inline_tokens(INLINE_TOKENS,
                                                              content)
                    if sandbox:
                        code = CommandCode.MARKDOWN_SANDBOX

                    inline = CommandLabel.INLINE in labels

                    discard_labels = self.discard_labels

                    all_notebooks = CommandLabel.ALL_NOTEBOOKS in labels
                    if all_notebooks:
                        # There are some exceptions here. A cell marked
                        # ALL_NOTEBOOKS will still not be copied if it's
                        # an ANSWER cell and the notebook is an EXERCISES
                        # notebook, or if it's a TO cell and the notebook
                        # is not an EXERCISES notebook.
                        if ((self.notebook_user == NotebookUser.EXERCISES) and
                            (CommandLabel.ANSWER in labels)):
                            all_notebooks = False
                        elif ((self.notebook_user != NotebookUser.EXERCISES) and
                              (CommandLabel.TODO in labels)):
                            all_notebooks = False

                    if all_notebooks:
                        # Remove ALL_NOTEBOOKS from the set of labels, so
                        # as not to befoul the screwed-up if statement,
                        # below. Leaving it in causes cells like this to be
                        # mishandled:
                        #
                        # %sql
                        # -- ANSWER (or -- TODO)
                        # -- ALL_NOTEBOOKS
                        labels = labels - {CommandLabel.ALL_NOTEBOOKS}

                    # This thing just gets uglier and uglier.
                    if ( (not (discard_labels & labels)) and
                         (((inline and code != self.notebook_code) or
                         ((not inline) and code == self.notebook_code)) or
                         all_notebooks)):

                        content = self.remove_and_replace(content, code, inline,
                                                          all_notebooks, is_first)

                        if CommandLabel.TEST in labels:
                            # Special handling.
                            content = self._handle_test_cell(cell_num, content)

                        isCodeCell = code != CommandCode.MARKDOWN

                        cell_split = command_cell
                        if is_IPython:
                            if isCodeCell:
                                cell_split = _code_cell
                            else:
                                cell_split = _markdown_cell

                        is_first = self._write_command(output, cell_split,
                                                       content, is_first)

                    elif CommandLabel.VIDEO in labels:
                        new_content = self._handle_video_cell(cell_num, content)
                        new_cell = [
                            '{0} MAGIC {1}'.format(self.base_comment, line)
                            for line in ['%md-sandbox'] + new_content
                        ]
                        is_first = self._write_command(
                            output, command_cell, new_cell + ['\n'], is_first
                        )

                # Optionally add the footer.
                if params.add_footer:
                    footer = params.notebook_footer.replace(
                        '\n', '\n{0} '.format(magic_prefix)
                    )
                    template = '\n{0} %md-sandbox\n{0} {1}'.format(
                        magic_prefix, footer
                    )
                    output.write(command_cell)
                    output.write(template)

            if is_IPython:
                self.generate_ipynb(file_out)

    def _handle_test_cell(self, cell_num, content):
        new_content = []
        for line in content:
            m = _test.match(line)
            if not m:
                new_content.append(line)
                continue

            remainder = line[m.end():].strip()
            if len(remainder) > 0:
                # There's already an annotation on the TEST marker.
                new_content.append(line)
            else:
                # Add the default annotation.
                new_content.append(line + " - " + DEFAULT_TEST_CELL_ANNOTATION)

        return new_content

    def _handle_video_cell(self, cell_num, content):
        new_content = []
        for line in content:
            m = _video.match(line)
            if not m:
                new_content.append(line)
                continue

            # The regular expression matches the first part of the token
            # (e.g., "-- VIDEO"). The remainder of the line constitutes
            # the arguments.
            arg_string = line[m.end():]
            if len(arg_string.strip()) == 0:
                raise Exception(
                    'Cell {0}: "{1}" is not of form: VIDEO <id> [<title>]'.format(
                    cell_num, line
                    )
                )

            args = arg_string.split(None, 1)
            (id, title) = args if len(args) == 2 else (args[0], "video")
            expanded = Template(VIDEO_TEMPLATE).safe_substitute({
                'title': title,
                'id':    id
            })
            new_content = new_content + expanded.split('\n')

        return new_content

    def _write_command(self, output, cell_split, content, is_first):
        if not is_first:
            output.write(cell_split)
        output.write('\n'.join(content))
        return False

    def trim_content(self, content):
        trim_top_lines = 0
        for line in content:
            if _command.match(line) or line.strip() == '':
                trim_top_lines += 1
                continue
            else:
                break
        content[:trim_top_lines] = []
        return content

    def generate_ipynb(self, file_out):
        """Generate an ipynb file based on a py IPython Notebook format.

        Note:
            IPython Noteboook py format based off of details found at:
            http://ipython.org/ipython-doc/1/interactive/nbconvert.html

        Args:
            file_out (str): The name to use when outputting the ipynb file.

        """
        import nbformat
        from nbformat.v3.nbpy import PyReader

        with codecs.open(file_out, 'r', _file_encoding_out,
                         errors=_file_encoding_errors) as intermediate:
            nb = PyReader().read(intermediate)

        os.remove(file_out)

        with codecs.open(file_out, 'w', _file_encoding_out,
                         errors=_file_encoding_errors) as output:
            nbformat.write(nbformat.convert(nb, 4.0), output)

    def remove_and_replace(self, content, code, inline, all_notebooks, isFirst):
        # Make a copy of content as we iterate over it multiple times
        modified_content = content[:]

        modified_content = _transform_match(modified_content, self.remove)
        modified_content = _replace_text(modified_content, self.replace)

        if inline or all_notebooks: # add back MAGIC and %magic
            if self.notebook_kind == NotebookKind.DATABRICKS:
                line_start = 'MAGIC '
            else:
                line_start = ''

            # we usually capture a blank line after COMMAND that needs to be
            # skipped
            skip_one = 1 if modified_content[0] == '' else 0

            if self.notebook_kind == NotebookKind.DATABRICKS:
                # add % command (e.g. %md)
                s = Parser.code_to_magic[code]
                if not code.on_separate_line():
                    # Suppress the newline after the magic, and add the content
                    # here.
                    content = modified_content[skip_one]
                    del modified_content[skip_one]
                    modified_content.insert(skip_one, "{0} {1}".format(s, content))
                else:
                    modified_content.insert(skip_one, s)

            modified_content = [
                u'{0} {1}{2}'.format(self.base_comment, line_start, line)
                for line in modified_content[skip_one:-1]
            ]

            modified_content = (['']*(not (isFirst or skip_one)) +
                                ['']*skip_one + modified_content + [''])

        return modified_content

# -----------------------------------------------------------------------------
# Globals and Functions
# -----------------------------------------------------------------------------

_file_encoding_in =  DEFAULT_ENCODING_IN
_file_encoding_out = DEFAULT_ENCODING_OUT
_file_encoding_errors = 'strict'
_output_dir = DEFAULT_OUTPUT_DIR
_be_verbose = False
_show_debug = False

def _debug(msg):
    if _show_debug:
        print("master_parse: (DEBUG) {0}".format(msg))

def _verbose(msg):
    if _be_verbose:
        print("master_parse: {0}".format(msg))


# Regular Expressions
_comment = r'(#|//|--)' # Allow Python, Scala, and SQL style comments
_line_start = r'\s*{0}+\s*'.format(_comment)  # flexible format
_line_start_restricted = r'\s*{0}\s*'.format(_comment)  # only 1 comment allowed


def or_magic(re_text):
    """Create a regular expression for matching MAGIC (%cells) and code cells.

    Args:
        re_text (str): The additional text that specifies the particular
                          content we are looking to match.

    Returns:
        str: A string that can be used with re that matches either lines that
             start with DBC's markdown or code cell formats.
    """
    # require a comment char before these entries
    re_text = make_re_text(re_text)
    return re.compile(r'({0}|{1})'.format(make_magic_text(re_text), re_text))


def make_re_text(regexText):
    """
    Create regular expression text that matches a comment and the
    expression w/ spaces.
    """
    return r'{0}{1}'.format(_line_start_restricted, regexText)


def make_re(regexText):
    return re.compile(make_re_text(regexText))


def make_magic_text(regexText):
    return r'{0}MAGIC{1}'.format(_line_start_restricted, regexText)


def make_magic(regex_token, must_be_word=False):
    '''
    Maps a "magic" regex into one that matches properly and preserves what
    follows the token.

    :param regex_token:   the regular expression text pattern for the token
    :param must_be_word:  whether the token must be a word by itself. This
                          should have been the default, when the tool was
                          originally written, but it wasn't. This option
                          defaults to False to limit possible regression.
                          But, some tokens (especially those with common
                          prefixes, like "%md" and "%md-sandbox") will need
                          to use True here.
    :return: A compiled regex
    '''
    if must_be_word:
        # This is complicated. Basically, the constructed regex says, "the
        # token must match at the end of the string (\Z) OR must be followed
        # by a white space character (\s). The (?:...) construct allows the
        # alternation (the OR), without creating a capture group.
        #
        # If you don't understand this, DON'T modify it until you do. It's
        # fragile.
        adj_token = regex_token + '(?:\Z|\s+)'
    else:
        adj_token = regex_token

    # Allow surrounding white space.
    regex_text = r'\s*' + adj_token + r'\s*(.*)$'
    return re.compile(make_magic_text(regex_text))


_databricks = make_re(r'Databricks')
_command = make_re(r'COMMAND')

_answer = or_magic(CommandLabel.ANSWER.value)
_private_test = or_magic(CommandLabel.PRIVATE_TEST.value)
_todo = or_magic(CommandLabel.TODO.value)
_dbc_only = or_magic(CommandLabel.DATABRICKS_ONLY.value)
_ipython_only = or_magic(CommandLabel.IPYTHON_ONLY.value)
_python_only = or_magic(CommandLabel.PYTHON_ONLY.value)
_scala_only = or_magic(CommandLabel.SCALA_ONLY.value)
_sql_only = or_magic(CommandLabel.SQL_ONLY.value)
_r_only = or_magic(CommandLabel.R_ONLY.value)
_new_part = or_magic(r'NEW_PART')
_inline = or_magic(CommandLabel.INLINE.value)
_all_notebooks = or_magic(CommandLabel.ALL_NOTEBOOKS.value)
_instructor_note = or_magic(CommandLabel.INSTRUCTOR_NOTE.value)
_video = or_magic(CommandLabel.VIDEO.value)
_test = or_magic(CommandLabel.TEST.value)

_ipython_remove_line = re.compile(
    r'.*{0}\s*REMOVE\s*LINE\s*IPYTHON\s*$'.format(_comment)
)

_markdown = make_magic(r'%md', must_be_word=True)
_markdown_sandbox = make_magic(r'%md-sandbox', must_be_word=True)
_scala = make_magic(r'%scala')
_python = make_magic(r'%python')
_r = make_magic(r'%r', must_be_word=True)
_file_system = make_magic(r'%fs')
_shell = make_magic(r'%sh')
_run = make_magic(r'%run', must_be_word=True)
_sql = make_magic(r'%sql')
_magic = re.compile(r'MAGIC ')

_markdownMagic = re.compile('^' + _line_start_restricted + r'MAGIC ')

# Replace
_ipythonReplaceRemoveLine = re.compile(
    r'{0}\s*REMOVE\s*LINE\s*IPYTHON\s*$'.format(_comment)
)
_display = re.compile(r'display\(.*?\)')
_hdr_3_replace = (re.compile(r'(^###(?=[^#])|(?<=[^#])###(?=[^#]))'), '##')
_hdr_4_replace = (re.compile(r'(^####(?=[^#])|(?<=[^#])####(?=[^#]))'), '###')
_hdr_4_gone = (re.compile(r'(^####\s*(?=[^#])|(?<=[^#])####\s*(?=[^#]))'), '\n')
_hdr_5_replace = (re.compile(r'(^#####(?=[^#])|(?<=[^#])#####(?=[^#]))'),
                  '####')
_mathjax_inline_replace = (re.compile(r'(%\(|\)%)'), '$')
_math_jax_equation_replace = (re.compile(r'(%\[|\]%)'), '$$')
_magic_replace = (re.compile(_line_start_restricted + r'MAGIC '), '')

_mathjax_replace1 = (re.compile(r'%\('), r'\\\\(')
_mathjax_replace2 = (re.compile(r'\)%'), r'\\\\)')
_mathjax_replace3 = (re.compile(r'%\['), r'\\\\[')
_mathjax_replace4 = (re.compile(r'\]%'), r'\\\\]')


# Renaming
_rename_public_test = (re.compile(r'PublicTest\.'), 'Test.')
_rename_import_public_test = (re.compile(r'import\s*PublicTest'), 'import Test')

# For ipynb Creation

_for_display = '\n# <codecell>\ndef display(*args, **kargs): pass\n'
_header = '# -*- coding: utf-8 -*-\n# <nbformat>3.0</nbformat>' + _for_display

_markdown_cell = '\n# <markdowncell>\n'
_code_cell = '\n# <codecell>\n'

_command_cell = '\n{0} COMMAND ----------\n'  # Replace {0} with comment prefix


def _regex_list_match(line, regexList):
    """
    Whether or not the line is matched by one or more regular expressions in
    the list.

    Args:
        line (str): The line to check for matches.
        regexList (list[_sre_SRE_Pattern]): A list of compiled regular
            expressions to match against.

    Returns:
        the match, or None
    """
    for regex in regexList:
        m = regex.match(line)
        if m:
            return m
    return None


def _transform_match(lines, regexList):
    """
    Transform or remove any line in lines that matches one of the regular
    expressions in the list.

    Args:
        lines (list[str]): A list of strings to check against the
            regular expression list.
        regexList (list[_sre_SRE_Pattern]): A list of compiled regular
            expressions to match against.

    Returns:
        list[str]: A new list of strings with all of the lines that match
            regular expressions removed.
    """
    res = []
    for line in lines:
        m = _regex_list_match(line, regexList)
        if m:
            remainder = m.group(2)
            if remainder:
                remainder = remainder.strip()
                if len(remainder) > 0:
                    res.append(remainder)
        else:
            res.append(line)
    return res


def _replace_line(line, regex_replace_list):
    """Replace any regular expression search matches with the provided string.

    Args:
        line (str): The line to check for matches that will be replaced.
        regeReplacexList (list[tuple[_sre_SRE_Pattern, str]]): A list of tuples
            containing a pair consisting of a compiled regular expression and
            the string to be used to replace matches.

    Returns:
        str: A string where all of the matches for the regular expressions have
             been replaced by the values provided.
    """
    for regex, value in regex_replace_list:
        line = re.sub(regex, value, line)
    return line


def _replace_text(lines, regex_replace_list):
    """
    Replace regular expression search matches with the provided string for
    all lines.

    Args:
        lines (list[str]): A list of strings to check against the regular
            expressions.
        regeReplacexList (list[tuple[_sre_SRE_Pattern, str]]): A list of tuples
            containing a pair consisting of a compiled regular expression and
            the string to be used to replace matches.

    Returns:
        list[str]: A new list of strings with all of the matches replaced by
        the provided values.
    """
    return [_replace_line(line, regex_replace_list) for line in lines]

_code_to_comment = {CommandCode.SQL: '--',
                    CommandCode.R: '#',
                    CommandCode.SCALA: '//',
                    CommandCode.PYTHON: '#'}

class ParseState(object):
    '''
    Used internally by the Parser class to track parsing state.
    '''
    def __init__(self):
        self.reset()

    def reset(self):
        self.command_content = []
        self.command_code = None
        self.command_labels = set()
        self.starting_line_number = None

    def __str__(self):
        return (
            "ParseState" +
            "<command_content={0}, " +
            "command_code={1}, " +
            "command_labels={2},"
            "starting_line_number={3}>"
        ).format(
            self.command_content, self.command_code, self.command_labels,
            self.starting_line_number
        )

    def __repr__(self):
        return self.__str__()


class Parser:
    """Customizable parser of DBC py files, converting to other formats.
    """

    pattern_to_label = [(_private_test, CommandLabel.PRIVATE_TEST),
                        (_answer, CommandLabel.ANSWER),
                        (_todo, CommandLabel.TODO),
                        (_inline, CommandLabel.INLINE),
                        (_dbc_only, CommandLabel.DATABRICKS_ONLY),
                        (_ipython_only, CommandLabel.IPYTHON_ONLY),
                        (_scala_only, CommandLabel.SCALA_ONLY),
                        (_python_only, CommandLabel.PYTHON_ONLY),
                        (_r_only, CommandLabel.R_ONLY),
                        (_all_notebooks, CommandLabel.ALL_NOTEBOOKS),
                        (_instructor_note, CommandLabel.INSTRUCTOR_NOTE),
                        (_file_system, CommandLabel.ALL_NOTEBOOKS),
                        (_shell, CommandLabel.ALL_NOTEBOOKS),
                        (_video, CommandLabel.VIDEO),
                        (_test, CommandLabel.TEST),
                        (_sql_only, CommandLabel.SQL_ONLY)]

    pattern_to_code = [(_markdown, CommandCode.MARKDOWN),
                       (_markdown_sandbox, CommandCode.MARKDOWN_SANDBOX),
                       (_scala, CommandCode.SCALA),
                       (_python, CommandCode.PYTHON),
                       (_file_system, CommandCode.FILESYSTEM),
                       (_shell, CommandCode.SHELL),
                       (_run, CommandCode.RUN),
                       (_sql, CommandCode.SQL),
                       (_r, CommandCode.R)]

    extension_to_code = {'.sql': CommandCode.SQL,
                         '.r': CommandCode.R,
                         '.scala': CommandCode.SCALA,
                         '.py': CommandCode.PYTHON}

    code_to_extension = {v: k for k, v in extension_to_code.items()}

    master_code = {CommandCode.SQL,
                   CommandCode.R,
                   CommandCode.SCALA,
                   CommandCode.PYTHON}

    code_to_pattern = {code: pattern for pattern, code in pattern_to_code}

    code_to_magic = {CommandCode.MARKDOWN: '%md',
                     CommandCode.MARKDOWN_SANDBOX: '%md-sandbox',
                     CommandCode.RUN: '%run',
                     CommandCode.SCALA: '%scala',
                     CommandCode.PYTHON: '%python',
                     CommandCode.FILESYSTEM: '%fs',
                     CommandCode.SHELL: '%sh',
                     CommandCode.SQL: '%sql',
                     CommandCode.R: '%r'}

    def __init__(self):
        """
        Initialize the defining attributes of this Parser.
        """
        self.base_notebook_code = None
        self.part = 0
        self.header = None

    def generate_commands(self, file_name):
        """Generates file content for DBC and ipynb use.

        Note:
            If file for output already exists in the current working directory
            it will be overwritten.

        Args:
            file_name (str): The name of the input file that has been exported
            from DBC in py format.

        Returns:
            tuple[str, list[Command]]: A tuple containing the header and a list
            of commands.
        """

        current = ParseState()

        def extend_content(cell_state):
            _debug('Notebook "{0}": Cell at line {1} matches labels {2}'.
                format(
                    file_name,
                    cell_state.starting_line_number,
                    [l.value for l in cell_state.command_labels]
                )
            )
            if cell_state.command_code is None:
                cell_state.command_code = self.base_notebook_code
            else:  # Remove %sql, %fs, etc and MAGIC
                pat = Parser.code_to_pattern[current.command_code]
                cell_state.command_content = _transform_match(
                    cell_state.command_content, [pat]
                )
                cell_state.command_content = _replace_text(
                    cell_state.command_content, [_magic_replace]
                )

            if cell_state.command_code not in Parser.master_code:
                # non base notebook commands are inlined automatically
                cell_state.command_labels.add(CommandLabel.INLINE)

            cmd = Command(self.part,
                          cell_state.command_code,
                          cell_state.command_labels,
                          cell_state.command_content)
            commands.append(cmd)

        _, file_extension = os.path.splitext(file_name)
        file_extension = file_extension.lower()

        assert file_extension in Parser.extension_to_code, \
            'Bad file extension for {0}'.format(file_name)
        self.base_notebook_code = Parser.extension_to_code[file_extension]
        base_comment = _code_to_comment[self.base_notebook_code]

        with codecs.open(file_name, 'r', _file_encoding_in,
                         errors=_file_encoding_errors) as dbcExport:
            file_contents = dbcExport.readlines()

        commands = []
        current.reset()
        self.part = 0

        line_number_inc = 1
        if len(file_contents) > 0 and _databricks.match(file_contents[0]):
            self.header = file_contents[0]
            # Strip first line if it's the Databricks' timestamp
            file_contents[:1] = []
            line_number_inc += 1

        for i, line in enumerate(file_contents):

            line_number = i + line_number_inc

            if current.starting_line_number is None:
                current.starting_line_number = line_number

            if _command.match(line):
                # New cell. Flush the current one.
                if len(current.command_content) > 0:
                    extend_content(current)

                current.reset()
                continue

            if _new_part.match(line):
                self.part += 1

            # Does this line match any of our special comment strings?
            for pat, label in Parser.pattern_to_label:
                if pat.match(line):
                    if label in DEPRECATED_LABELS:
                        print(
                            '*** "{0}", line {1}: WARNING: "{2}" is deprecated.'
                                .format(file_name, line_number, label.value)
                        )
                    current.command_labels.add(label)

            # Does this line match any of the Databricks magic cells?
            for pat, code in Parser.pattern_to_code:
                line2 = line.rstrip()
                m = pat.match(line2)
                if m:
                    if current.command_code is not None:
                        msg = '"{0}", line {1}: multiple magic strings.'.format(
                            file_name, line_number
                        )
                        raise Exception(msg)
                    current.command_code = code

            line = line.rstrip("\r\n")
            # Lines with only MAGIC do not reimport
            if len(line) <= 8 and line[-5:] == 'MAGIC':
                # Keep empty lines
                current.command_content.append(base_comment + ' MAGIC ')
            else:
                current.command_content.append(line)

        # Flush anything left.
        if len(current.command_content) > 0:
            current.command_content.append("")
            extend_content(current)

        return self.header, commands


class UsageError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


def process_notebooks(params):
    """
    Main entry point for notebook processing. This function can be used to
    process notebook from within another Python program.

    :param params: parameters
    :return: Nothing.
    """
    global _output_dir, _file_encoding_in, _file_encoding_out
    _output_dir = params.output_dir
    _file_encoding_in = params.encoding_in
    _file_encoding_out = params.encoding_out

    global _be_verbose
    _be_verbose = params.enable_verbosity

    global _show_debug
    _show_debug = params.enable_debug

    if not (params.databricks or params.ipython):
        raise UsageError("Specify at least one of databricks or ipython")
    if not (params.scala or params.python or params.r or params.sql):
        raise UsageError("Specify at least one of Scala, Python, R or SQL")
    if not (params.instructor or params.answers or params.exercises):
        raise UsageError("Specify at least one of: instructor, answers, exercises")

    if os.path.isdir(params.path):
        files = []
        for p in ['*.py', '*.scala', '*.r', '*.sql']:
            files.extend(glob.glob(os.path.join(path, p)))
    else:
        files = [params.path]

    if not files:
        raise UsageError("No acceptable files found for {0}".format(params.path))

    notebook_kinds = []
    if params.databricks:
        notebook_kinds.append(NotebookKind.DATABRICKS)
    if params.ipython:
        notebook_kinds.append(NotebookKind.IPYTHON)

    notebook_users = []
    if params.instructor:
        notebook_users.append(NotebookUser.INSTRUCTOR)
    if params.exercises:
        notebook_users.append(NotebookUser.EXERCISES)
    if params.answers:
        notebook_users.append(NotebookUser.ANSWERS)

    notebook_languages = []
    if params.scala:
        notebook_languages.append(CommandCode.SCALA)
    if params.python:
        notebook_languages.append(CommandCode.PYTHON)
    if params.r:
        notebook_languages.append(CommandCode.R)
    if params.sql:
        notebook_languages.append(CommandCode.SQL)

    if params.ipython and CommandCode.PYTHON not in notebook_languages:
        langs = []
        for x in notebook_languages: langs.append(Parser.code_to_extension[x])
        raise UsageError('IPython target can only be used when generating' + \
                         'Python. Languages found: ' + ", ".join(langs))

    notebooks = []
    for kind in notebook_kinds:
        for user in notebook_users:
            for lang in notebook_languages:
                if kind != NotebookKind.IPYTHON or \
                   (kind == NotebookKind.IPYTHON and lang == CommandCode.PYTHON):
                    notebooks.append(NotebookGenerator(kind, user, lang, params))

    parser = Parser()
    for db_src in files:
        header, commands = parser.generate_commands(db_src)
        for notebook in notebooks:
            notebook.generate(header, commands, db_src, params)


def main():
    import argparse
    import sys

    arg_parser = argparse.ArgumentParser()
    version_or_file = arg_parser.add_mutually_exclusive_group()
    version_or_file.add_argument('filename',
                                 nargs='?',
                                 help='enter either a filename or a directory')
    version_or_file.add_argument("-V", "--version",
                                 help="Show version and exit",
                                 action='store_true')

    targetGroup = arg_parser.add_argument_group('target')
    targetGroup.add_argument('-db', '--databricks',
                             help='generate databricks notebook(s)',
                             action='store_true')
    targetGroup.add_argument('-ip', '--ipython',
                             help='generate ipython notebook(s)',
                             action='store_true')
    codeGroup = arg_parser.add_argument_group('code')
    codeGroup.add_argument('-sc', '--scala',
                           help='generate scala notebook(s)',
                           action='store_true')
    codeGroup.add_argument('-py', '--python',
                           help='generate python notebook(s)',
                           action='store_true')
    codeGroup.add_argument('-r', '--rproject',
                           help='generate r notebook(s)',
                           action='store_true')
    codeGroup.add_argument('-sq', '--sql',
                           help='generate sql notebook(s)',
                           action='store_true')
    userGroup = arg_parser.add_argument_group('user')
    userGroup.add_argument('-in', '--instructor',
                           help='generate instructor notebook(s)',
                           action='store_true')
    userGroup.add_argument('-ex', '--exercises',
                           help='generate exercises notebook(s)',
                           action='store_true')
    userGroup.add_argument('-an', '--answers',
                           help='generate answers notebook(s)',
                           action='store_true')
    arg_parser.add_argument('-cc', '--creativecommons',
                            help='add by-nc-nd cc 4.0 license',
                            action='store_true')
    arg_parser.add_argument('-ei', '--encoding-in',
                            help="input file encoding",
                            action='store',
                            default=DEFAULT_ENCODING_OUT,
                            metavar="ENCODING")
    arg_parser.add_argument('-eo', '--encoding-out',
                            help="output file encoding",
                            action='store',
                            default=DEFAULT_ENCODING_OUT,
                            metavar="ENCODING")
    arg_parser.add_argument('--copyright',
                            help='Set the copyright year for any generated ' +
                                 'copyright notices. Default is current year.',
                            default=datetime.now().year,
                            action='store',
                            metavar='YEAR')
    arg_parser.add_argument('-nf', '--notebook-footer',
                            help='A file containing Markdown and/or HTML, to ' +
                                 'be used as the bottom-of-notebook footer, ' +
                                 'if headings are enabled. If not specified, ' +
                                 'an internal default (a copyright footer) ' +
                                 'is used. See also --footer and --copyright.',
                            default=None,
                            metavar="<file>")
    arg_parser.add_argument('--footer',
                            help='By default, even if you specify -nf, this ' +
                                 'tool does not add the notebook footer to ' +
                                 'bottom of generated notebooks. If you ' +
                                 'specify this option, it will do so.',
                            action='store_true')
    arg_parser.add_argument('-nh', '--notebook-heading',
                            help='A file containing Markdown and/or HTML, ' +
                                 'to be used as the top-of-notebook heading, ' +
                                 'if headings are enabled. If not specified, ' +
                                 'an internal default is used. See also ' +
                                 '--heading.',
                            default=None,
                            metavar="<file>")
    arg_parser.add_argument('--heading',
                            help='By default, even if you specify -nh, this ' +
                                 'tool does not add the notebook heading to ' +
                                 'top of generated notebooks. If you specify ' +
                                 'this option, it will do so.',
                            action='store_true')
    arg_parser.add_argument('-d', '--dir',
                            help="Base output directory. Default: {0}".format(
                                DEFAULT_OUTPUT_DIR),
                            action='store',
                            dest='output_dir',
                            metavar="OUTPUT_DIR")
    arg_parser.add_argument('-D', '--debug',
                            help="Enable debug messages",
                            action='store_true')
    arg_parser.add_argument('-v', '--verbose',
                            help="Enable verbose messages.",
                            action='store_true')

    args = arg_parser.parse_args()

    if args.version:
        print('Master Parse tool, version {0}'.format(VERSION))
        sys.exit(0)

    if not (args.databricks or args.ipython):
        arg_parser.error('at least one of -db or -ip is required')

    if not (args.scala or args.python or args.rproject or args.sql):
        arg_parser.error('at least one of -sc, -py, -r, or -sq is required')

    if not (args.instructor or args.exercises or args.answers):
        arg_parser.error('at least one of -in, -ex or -an is required')

    if not args.filename:
        arg_parser.error('Missing notebook path.')

    params = Params(
        path=args.filename,
        output_dir=args.output_dir,
        databricks=args.databricks,
        ipython=args.ipython,
        scala=args.scala,
        python=args.python,
        r=args.rproject,
        sql=args.sql,
        instructor=args.instructor,
        answers=args.answers,
        exercises=args.exercises,
        creative_commons=args.creativecommons,
        notebook_heading_path=args.notebook_heading,
        add_heading=args.heading,
        notebook_footer_path=args.notebook_footer,
        add_footer=args.footer,
        encoding_in=args.encoding_in,
        encoding_out=args.encoding_out,
        enable_verbosity=args.verbose,
        enable_debug=args.debug,
        copyright_year=args.copyright
    )

    try:
        process_notebooks(params)
    except UsageError as e:
        sys.stderr.write(e.message + '\n')
        sys.exit(1)

if __name__ == '__main__':
    main()
