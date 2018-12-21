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
from string import Template as StringTemplate
from InlineToken import InlineToken, expand_inline_tokens
from datetime import datetime
from textwrap import TextWrapper
from random import SystemRandom

VERSION = "1.19.0"

# -----------------------------------------------------------------------------
# Enums. (Implemented as classes, rather than using the Enum functional
# API, for ease of modification.)
# -----------------------------------------------------------------------------

class TargetProfile(Enum):
    '''
    The target output profile, currently either AZURE or AMAZON.
    '''
    AZURE = 'azure'
    AMAZON = 'amazon'
    NONE = 'none'

class CourseType(Enum):
    '''Type of course (ILT or self-paced)'''
    SELF_PACED = 'self-paced'
    ILT = 'ilt'
    NONE = 'none'

# Strictly speaking, this is not an enum, but it's here for convenience.
# It maps target profile values to their in-cell keywords.

LABEL_TO_TARGET_PROFILE = {
    '{}_ONLY'.format(t.value.upper()): t for t in TargetProfile
    if t is not TargetProfile.NONE
}

TARGET_PROFILE_TO_LABEL = {
    v: k for k, v in LABEL_TO_TARGET_PROFILE.items()
}

# NOTE: If you add a new label, be sure to look at:
#
# - Notebook.generate
# - Notebook._get_keep_labels()
# - self.remove in Notebook.__init__()
# - the regular expressions for the tags (search for "CommandLabel regexes")
class CommandLabel(Enum):
    IPYTHON_ONLY      = 'IPYTHON_ONLY'
    PYTHON_ONLY       = 'PYTHON_ONLY'
    SCALA_ONLY        = 'SCALA_ONLY'
    R_ONLY            = 'R_ONLY'
    SQL_ONLY          = 'SQL_ONLY'
    ANSWER            = 'ANSWER'
    TODO              = 'TODO'
    AZURE_ONLY        = TARGET_PROFILE_TO_LABEL[TargetProfile.AZURE]
    AMAZON_ONLY       = TARGET_PROFILE_TO_LABEL[TargetProfile.AMAZON]
    TEST              = 'TEST'
    PRIVATE_TEST      = 'PRIVATE_TEST'
    DATABRICKS_ONLY   = 'DATABRICKS_ONLY'
    INLINE            = 'INLINE'
    ALL_NOTEBOOKS     = 'ALL_NOTEBOOKS'
    INSTRUCTOR_NOTE   = 'INSTRUCTOR_NOTE'
    VIDEO             = 'VIDEO'
    SOURCE_ONLY       = 'SOURCE_ONLY'
    ILT_ONLY          = 'ILT_ONLY'
    SELF_PACED_ONLY   = 'SELF_PACED_ONLY'

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

def _icon_image_url(image):
    return (
        'https://files.training.databricks.com/static/images/' +
        image
    )

def _label_for_course_type(course_type):
    if course_type == CourseType.SELF_PACED:
        return CommandLabel.SELF_PACED_ONLY
    if course_type == CourseType.ILT:
        return CommandLabel.ILT_ONLY
    assert(False)

INLINE_TOKENS = [
    InlineToken(
        title='Hint',
        tag=':HINT:',
        image=_icon_image_url('icon-light-bulb.svg'),
        template=r'<img alt="${title}" title="${title}" style="${style}" src="${image}"/>&nbsp;**${title}:**',
        style='height:1.75em; top:0.3em'
    ),
    InlineToken(
        title='Caution',
        tag=':CAUTION:',
        image=_icon_image_url('icon-warning.svg'),
        style='height:1.3em; top:0.0em'
    ),
    InlineToken(
        tag=':BESTPRACTICE:',
        title='Best Practice',
        image=_icon_image_url('icon-blue-ribbon.svg'),
        style='height:1.75em; top:0.3em'
    ),
    InlineToken(
        tag=':SIDENOTE:',
        title='Side Note',
        image=_icon_image_url('icon-note.webp'),
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
    CommandLabel.ILT_ONLY:        ALL_CELL_TYPES,
    CommandLabel.SELF_PACED_ONLY: ALL_CELL_TYPES,
    CommandLabel.SOURCE_ONLY:     ALL_CELL_TYPES,
    CommandLabel.DATABRICKS_ONLY: ALL_CELL_TYPES,
    CommandLabel.PYTHON_ONLY:     ALL_CELL_TYPES,
    CommandLabel.SCALA_ONLY:      ALL_CELL_TYPES,
    CommandLabel.R_ONLY:          ALL_CELL_TYPES,
    CommandLabel.SQL_ONLY:        ALL_CELL_TYPES,
    CommandLabel.ANSWER:          ALL_CELL_TYPES,
    CommandLabel.TODO:            CODE_CELL_TYPES,
    CommandLabel.TEST:            CODE_CELL_TYPES,
    CommandLabel.PRIVATE_TEST:    CODE_CELL_TYPES,
    CommandLabel.AMAZON_ONLY:     ALL_CELL_TYPES,
    CommandLabel.AZURE_ONLY:      ALL_CELL_TYPES,
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
'''<iframe  
src="//fast.wistia.net/embed/iframe/${id}?videoFoam=true"
style="border:1px solid #1cb1c2;"
allowtransparency="true" scrolling="no" class="wistia_embed"
name="wistia_embed" allowfullscreen mozallowfullscreen webkitallowfullscreen
oallowfullscreen msallowfullscreen width="640" height="360" ></iframe>
<div>
<a target="_blank" href="https://fast.wistia.net/embed/iframe/${id}?seo=false">
  <img alt="Opens in new tab" src="''' + _icon_image_url('external-link-icon-16x16.png') +
'''"/>&nbsp;Watch full-screen.</a>
</div>''')

VIDEO_CELL_CODE = CommandCode.MARKDOWN

INSTRUCTOR_NOTE_HEADING = '<h2 style="color:red">Instructor Note</h2>'

DEFAULT_NOTEBOOK_HEADING = """<div style="text-align: center; line-height: 0; padding-top: 9px;">
  <img src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png" alt="Databricks Learning" style="width: 600px; height: 163px">
</div>"""

DEFAULT_NOTEBOOK_FOOTER = """&copy; {copyright_year} Databricks, Inc. All rights reserved.<br/>
Apache, Apache Spark, Spark and the Spark logo are trademarks of the <a href="http://www.apache.org/">Apache Software Foundation</a>.<br/>
<br/>
<a href="https://databricks.com/privacy-policy">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use">Terms of Use</a> | <a href="http://help.databricks.com/">Support</a>"""

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
                 target_profile=TargetProfile.NONE,
                 course_type=CourseType.NONE,
                 notebook_heading_path=None,
                 encoding_in=DEFAULT_ENCODING_IN,
                 encoding_out=DEFAULT_ENCODING_OUT,
                 enable_verbosity=False,
                 enable_debug=False,
                 copyright_year=None,
                 enable_templates=False,
                 extra_template_vars=None):
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
        assert(course_type in set(CourseType))
        self.course_type = course_type
        assert(target_profile in set(TargetProfile))
        self.target_profile = target_profile
        self.enable_templates = enable_templates
        self.extra_template_vars = extra_template_vars or {}

        for purpose, file in (('Notebook footer', notebook_footer_path),
                              ('Notebook header', notebook_heading_path)):
            if file is not None:
                self._check_path(file, purpose)

    @property
    def notebook_footer(self):
        if self._notebook_footer is None:
            if self.notebook_footer_path is None:
                self._notebook_footer = DEFAULT_NOTEBOOK_FOOTER.format(
                    copyright_year=self.copyright_year
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
        :param notebook_code:  the code type of the notebook (Scala, R, etc.)
        :param params:         parsed (usually command-line) parameters
        '''
        base_keep = set(CommandLabel.__members__.values())
        self.keep_labels = self._get_keep_labels(params,
                                                 notebook_kind,
                                                 notebook_user,
                                                 notebook_code)
        # Discard any cells with a label that is not explicitly kept
        self.discard_labels = base_keep - self.keep_labels

        # In kept cells, remove the following labels from the content
        self.remove = [_dbc_only, _scala_only, _python_only, _new_part, _inline,
                       _all_notebooks, _instructor_note, _video,
                       _azure_only, _amazon_only, _ilt_only, _self_paced_only]

        self.replace = [(_ipythonReplaceRemoveLine, ''),
                        _rename_public_test,
                        _rename_import_public_test]
        self.notebook_kind = notebook_kind
        self.notebook_user = notebook_user
        self.notebook_code = notebook_code
        self.file_ext = self._get_extension()
        self.base_comment = _code_to_comment[self.notebook_code]
        self.params = params
        self.cell_template_processor = CellTemplateProcessor()

    def _get_keep_labels(self, params, *args):
        labels = {
            CommandLabel.TEST,
            CommandLabel.INLINE,
            CommandLabel.VIDEO
        }
        for arg in args:
            label = NotebookGenerator.param_to_label[arg]
            labels.update(label)

        # Keep the current content type:
        if params.course_type == CourseType.SELF_PACED:
            labels.add(CommandLabel.SELF_PACED_ONLY)
        elif params.course_type == CourseType.ILT:
            labels.add(CommandLabel.ILT_ONLY)

        # Don't discard the profile labels.
        for c in CommandLabel:
            tp = LABEL_TO_TARGET_PROFILE.get(c.value)
            if tp is not None:
                # This is a target profile label. Mark it as kept.
                labels.add(c)

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
        '''
        Generate output notebook.

        :param header:      the notebook header
        :param commands:    the array of Command objects
        :param input_name:  the source notebook name
        :param params:      parsed command line parameters
        :param parts:       whether to honor parts or not
        '''

        _verbose('Generating {0} notebook(s) for "{1}"'.format(
            str(self.notebook_user), input_name
        ))

        if params.enable_templates:
            # Process the cell as a template.
            new_commands = []
            for i, cmd in enumerate(commands):
                cell_num = i + 1
                if cmd.code.is_markdown():
                    (new_code, new_content) = self.cell_template_processor.process(
                        cmd.content, cmd.code, cell_num, input_name,
                        self.notebook_code, params,
                    )
                    new_commands.append(Command(
                        part=cmd.part,
                        code=new_code,
                        labels=cmd.labels,
                        content=new_content
                    ))
                else:
                    new_commands.append(cmd)
            commands = new_commands

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

                    if CommandLabel.SOURCE_ONLY in labels:
                        # Suppress this one. It's a source-only cell.
                        _debug("Cell #{} is source-only. Suppressing it.".format(
                            cell_num
                        ))
                        continue

                    if CommandLabel.INSTRUCTOR_NOTE in labels:
                        # Special case processing: Add instructor note heading,
                        # and force use of %md-sandbox

                        code = CommandCode.MARKDOWN_SANDBOX
                        content = (
                            [INSTRUCTOR_NOTE_HEADING] +
                            content
                        )

                    if CommandLabel.TODO in labels:
                        content = self._handle_todo_cell(cell_num, content)

                    if code in (CommandCode.MARKDOWN, CommandCode.MARKDOWN_SANDBOX):
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


                    # Check for target profile label.
                    remove_profile_cell = False
                    cell_profile_labels = []
                    for label in labels:
                        lv = label.value
                        cell_profile = LABEL_TO_TARGET_PROFILE.get(lv)
                        if cell_profile is None:
                            continue
                        cell_profile_labels.append(lv)

                        if ((params.target_profile is not TargetProfile.NONE) and
                            (cell_profile != params.target_profile)):
                            remove_profile_cell = True

                    if len(cell_profile_labels) > 1:
                        raise Exception(
                            'Cell {} in {} has multiple profile tags: {}'.format(
                                cell_num, input_name, ', '.join(cell_profile_labels)
                            )
                        )
                    if remove_profile_cell:
                        continue

                    # Process the cell.

                    if CommandLabel.VIDEO in labels:
                        # First, handle the video cell expansion. Then, handle
                        # the updated cell normally.
                        content = self._handle_video_cell(cell_num, content)
                        code = VIDEO_CELL_CODE
                        _debug('Preprocessing video cell {}'.format(cell_num))

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

    def _handle_todo_cell(self, cell_num, content):
        # Special case processing for runnable To-Do cells: If
        # every line in the cell starts with a comment character,
        # remove the leading comment characters.
        comment_start = re.compile(_comment_with_optional_blank)
        def starts_with_comment(line):
            if (comment_start.search(line) or
                    (len(line.strip()) == 0)):
                return True
            else:
                return False

        label_regexes = [t[0] for t in Parser.pattern_to_label]
        def matches_label(line):
            for r in label_regexes:
                if r.match(line):
                    return True
            return False

        if all_pred(starts_with_comment, content):
            _debug("Cell #{} is a runnable TODO cell.".format(cell_num))
            new_content = []
            for s in content:
                if matches_label(s):
                    # Don't edit labels.
                    new_content.append(s)
                elif len(s.strip()) == 0:
                    new_content.append(s)
                else:
                    # Remove leading comment.
                    m = comment_start.search(s)
                    assert m is not None
                    new_content.append(m.group(2))
            return new_content

        return content

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
            expanded = StringTemplate(VIDEO_TEMPLATE).safe_substitute({
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


class CellTemplateProcessor(object):
    '''
    Used to process cell Mustache templates.
    '''

    # The template for the JavaScript and the initial button that
    # precedes an expanded hints cell. This is a Mustache template.
    #
    # Expected variables:
    #
    # id_prefix - HTML ID prefix to use (string). Must correspond to the
    #             ID prefix used in the hints and the answer.
    HINTS_PRELUDE_TEMPLATE = \
'''<script type="text/javascript">
  window.onload = function() {
    var allHints = document.getElementsByClassName("hint-{{id_prefix}}");
    var answer = document.getElementById("answer-{{id_prefix}}");
    var totalHints = allHints.length;
    var nextHint = 0;
    var hasAnswer = (answer != null);
    var items = new Array();
    var answerLabel = "Click here for the answer";
    for (var i = 0; i < totalHints; i++) {
      var elem = allHints[i];
      var label = "";
      if ((i + 1) == totalHints)
        label = answerLabel;
      else
        label = "Click here for the next hint";
      items.push({label: label, elem: elem});
    }
    if (hasAnswer) {
      items.push({label: '', elem: answer});
    }

    var button = document.getElementById("hint-button-{{id_prefix}}");
    if (totalHints == 0) {
      button.innerHTML = answerLabel;
    }
    button.onclick = function() {
      items[nextHint].elem.style.display = 'block';
      if ((nextHint + 1) >= items.length)
        button.style.display = 'none';
      else
        button.innerHTML = items[nextHint].label;
        nextHint += 1;
    };
    button.ondblclick = function(e) {
      e.stopPropagation();
    }
    var answerCodeBlocks = document.getElementsByTagName("code");
    for (var i = 0; i < answerCodeBlocks.length; i++) {
      var elem = answerCodeBlocks[i];
      var parent = elem.parentNode;
      if (parent.name != "pre") {
        var newNode = document.createElement("pre");
        newNode.append(elem.cloneNode(true));
        elem.replaceWith(newNode);
        elem = newNode;
      }
      elem.ondblclick = function(e) {
        e.stopPropagation();
      };

      elem.style.marginTop = "1em";
    }
  };
</script>

<div>
  <button type="button" class="btn btn-light"
          style="margin-top: 1em"
          id="hint-button-{{id_prefix}}">Click here for a hint</button>
</div>
'''

    # The template for a single hint. This is a Mustache template.
    #
    # Expected variables:
    #
    # id_prefix - HTML ID prefix to use (string). Must correspond to the
    #             ID prefix used in the JavaScript and the answer.
    # hint      - the body of the hint
    HINT_TEMPLATE = \
'''<div class="hint-{{id_prefix}}" style="padding-bottom: 20px; display: none">
  Hint:
  <div style="margin-left: 1em">{{hint}}</div>
</div>
'''

    # The template for an expanded answer.
    #
    # Expected variables:
    #
    # answer    - the answer body
    # id_prefix - HTML ID prefix to use (string). Must correspond to the
    #             ID prefix used in the JavaScript and the hint(s).
    ANSWER_TEMPLATE = \
'''<div id="answer-{{id_prefix}}" style="padding-bottom: 20px; display: none">
  The answer:
  <div class="answer" style="margin-left: 1em">
{{answer}}
  </div>
</div>
'''

    # Regex patterns that match possible bad Mustache substitutions. The code
    # assumes all patterns have at one capture group containing the part that
    # mismatches.
    BAD_MUSTACHE_PATTERNS = (
        r'({{}})',                    # empty tag
        r'^({[#/]?[^{}]+}})',         # {tag}}, {#tag}}, {/tag}} at start
        r'^({[#/]?[^{}]+}})$',        # {tag}}, {#tag}}, {/tag}} at start & end
        r'[^{]({[#/]?[^{}]+}})',      # {tag}}, {#tag}}, {/tag}} elsewhere
        r'^[^{]({{[#/]?[^{}]+})$',    # {{tag}, {{#tag}, {{/tag} at start & end
        r'[^{]({{[#/]?[^{}]+})$',     # {{tag}, {{#tag}, {{/tag} at end
        r'[^{]({{[#/]?[^{}]+})[^}]',  # {{tag}, {{#tag}, {{/tag} elsewhere
    )

    BAD_MUSTACHE_REGEXPS = [re.compile(s) for s in BAD_MUSTACHE_PATTERNS]

    def __init__(self):
        import pystache

        self._id_prefix = None
        self._found_hints = False
        self._in_hints_block = False
        self._total_hints = 0
        # Use an instantiated pystache.Renderer() object, rather than the
        # pystache.render() function, because the object generates better
        # errors.
        self._renderer = pystache.Renderer(missing_tags='strict')

    def process(self, contents, cell_code, cell_num, notebook_name,
                language, params):
        '''
        Runs a cell's content through the template processor.

        :param contents:      the contents, a list of lines with no trailing
                              newline
        :param cell_code:     the cell code (CommandCode.MARKDOWN,
                              CommandCode.MARKDOWN_SANDBOX)
        :param cell_num:      the cell number, for errors/warnings
        :param notebook_name: name of notebook, for errors/warnings
        :param language:      output language (as a CommandCode) of the
                              notebook being generated
        :param params:        the parsed command line parameters

        :return: a tuple with two elements: the possibly-changed command code
                 (because certain expansions only work in %md-sandbox) and the new
                 content as a list of lines with no trailing newline
        '''
        self._found_hints = False
        self._in_hints_block = False
        self._total_hints = 0

        s = '\n'.join(contents)
        if params.target_profile == TargetProfile.NONE:
            amazon = ''
            azure = ''
        elif params.target_profile == TargetProfile.AMAZON:
            amazon = 'Amazon'
            azure = ''
        else:
            amazon = ''
            azure = 'Azure'

        scala = False
        python = False
        r = False
        sql = False
        if language == CommandCode.SQL:
            lang_string = "SQL"
            sql = True
        elif language == CommandCode.SCALA:
            lang_string = "Scala"
            scala = True
        elif language == CommandCode.PYTHON:
            lang_string = "Python"
            python = True
        elif language == CommandCode.R:
            lang_string = "R"
            r = True
        else:
            lang_string = ""

        def check_for_bad_tags(s):
            bad = False
            lines = s.split('\n')
            for i, line in enumerate(lines):
                line_num = i + 1
                for r in self.BAD_MUSTACHE_REGEXPS:
                    m = r.search(line)
                    if m:
                        _warning(('"{}", cell #{}, line {}: Possibly bad ' +
                                  'Mustache tag "{}".').format(
                            notebook_name, cell_num, line_num, m.group(1)
                        ))
                        bad = True
            return bad

        def strip_leading_and_trailing_blank_lines(text):
            import itertools

            def drop_leading(lines):
                return list(itertools.dropwhile(lambda s: len(s.strip()) == 0, lines))

            lines = drop_leading(text.split('\n'))
            lines.reverse()
            lines = drop_leading(lines)
            lines.reverse()
            return '\n'.join(lines)


        def handle_hints(text):
            # Emit the prelude, which contains the JavaScript and the button.
            # Then, pass the text along, for further expansion.
            self._id_prefix = str(_rng.randint(0, 10000))
            self._found_hints = True
            self._in_hints_block = True
            prelude_vars = {
                'id_prefix': self._id_prefix
            }
            prelude = self._renderer.render(
                self.HINTS_PRELUDE_TEMPLATE, prelude_vars
            )
            return prelude + strip_leading_and_trailing_blank_lines(text)

        def handle_hint(text):
            # The text is the body of the hint. Expand the hints template.
            if not self._in_hints_block:
                raise Exception('Found {{#HINT}} outside required {{#HINTS}} block.')

            self._total_hints += 1
            hint_vars = {
                'id_prefix': self._id_prefix,
                'hint':      strip_leading_and_trailing_blank_lines(text)
            }
            return self._renderer.render(self.HINT_TEMPLATE, hint_vars)

        def handle_answer(text):
            # The text is the body of the answer.

            vars = {
                'id_prefix': self._id_prefix
            }

            # Render the answer template.
            vars['answer'] = strip_leading_and_trailing_blank_lines(text)
            return self._renderer.render(self.ANSWER_TEMPLATE, vars)

        if params.course_type == CourseType.SELF_PACED:
            self_paced = True
            ilt = False
        elif params.course_type == CourseType.ILT:
            self_paced = False
            ilt = True
        else:
            self_paced = False
            ilt = False

        vars = {
            'amazon':            amazon,
            'azure':             azure,
            'copyright_year':    params.copyright_year,
            'notebook_language': lang_string,
            'HINT':              handle_hint,
            'HINTS':             handle_hints,
            'ANSWER':            handle_answer,
            'r':                 r,
            'scala':             scala,
            'python':            python,
            'sql':               sql,
            'ilt':               ilt,
            'self_paced':        self_paced,
        }

        vars.update(params.extra_template_vars)
        check_for_bad_tags(s)
        new_content = self._renderer.render(s, vars)

        if self._found_hints:
            new_cell_code = CommandCode.MARKDOWN_SANDBOX
        else:
            new_cell_code = cell_code

        return (new_cell_code, new_content.split('\n'))


# -----------------------------------------------------------------------------
# Globals and Functions
# -----------------------------------------------------------------------------

_file_encoding_in =  DEFAULT_ENCODING_IN
_file_encoding_out = DEFAULT_ENCODING_OUT
_file_encoding_errors = 'strict'
_output_dir = DEFAULT_OUTPUT_DIR
_be_verbose = False
_show_debug = False
_rng = SystemRandom()

COLUMNS = int(os.getenv('COLUMNS', '80')) - 1
DEBUG_PREFIX = "master_parse (DEBUG) "
VERBOSE_PREFIX = "master_parse: "
WARNING_PREFIX = "master_parse: (WARNING) "

# Text wrappers

_warning_wrapper = TextWrapper(width=COLUMNS,
                               subsequent_indent=' ' * len(WARNING_PREFIX))

_verbose_wrapper = TextWrapper(width=COLUMNS,
                               subsequent_indent=' ' * len(VERBOSE_PREFIX))

_debug_wrapper = TextWrapper(width=COLUMNS,
                             subsequent_indent=' ' * len(DEBUG_PREFIX))

def _warning(msg):
    print(_warning_wrapper.fill("{0}{1}".format(WARNING_PREFIX, msg)))

def _debug(msg):
    if _show_debug:
        print(_debug_wrapper.fill("{0}{1}".format(DEBUG_PREFIX, msg)))


def _verbose(msg):
    if _be_verbose:
        print(_verbose_wrapper.fill("{0}{1}".format(VERBOSE_PREFIX, msg)))


# Regular Expressions
_comment = r'(#|//|--)' # Allow Python, Scala, and SQL style comments
_comment_with_optional_blank = r'^\s*(#|//|--)\s?(.*)$'
_line_start = r'\s*{0}+\s*'.format(_comment)  # flexible format
_line_start_restricted = r'\s*{0}\s*'.format(_comment)  # only 1 comment allowed

# COPIED FROM bdc CODE. Should be shared, but there's no simple way to do that
# right now.
def all_pred(func, iterable):
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

# CommandLabel regexes
#
# See also the Parser class.
_answer = or_magic(CommandLabel.ANSWER.value)
_private_test = or_magic(CommandLabel.PRIVATE_TEST.value)
_todo = or_magic(CommandLabel.TODO.value)
_dbc_only = or_magic(CommandLabel.DATABRICKS_ONLY.value)
_ipython_only = or_magic(CommandLabel.IPYTHON_ONLY.value)
_python_only = or_magic(CommandLabel.PYTHON_ONLY.value)
_scala_only = or_magic(CommandLabel.SCALA_ONLY.value)
_amazon_only = or_magic(CommandLabel.AMAZON_ONLY.value)
_azure_only = or_magic(CommandLabel.AZURE_ONLY.value)
_ilt_only = or_magic(CommandLabel.ILT_ONLY.value)
_self_paced_only = or_magic(CommandLabel.SELF_PACED_ONLY.value)
_source_only = or_magic(CommandLabel.SOURCE_ONLY.value)
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
                        (_amazon_only, CommandLabel.AMAZON_ONLY),
                        (_azure_only, CommandLabel.AZURE_ONLY),
                        (_ilt_only, CommandLabel.ILT_ONLY),
                        (_self_paced_only, CommandLabel.SELF_PACED_ONLY),
                        (_source_only, CommandLabel.SOURCE_ONLY),
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

    def generate_commands(self, file_name, params):
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

    if (params.course_type is None) or (params.course_type == CourseType.NONE):
        raise UsageError('course_type must be set.')
    if not (params.databricks or params.ipython):
        raise UsageError("Specify at least one of databricks or ipython")
    if not (params.scala or params.python or params.r or params.sql):
        raise UsageError("Specify at least one of Scala, Python, R or SQL")
    if not (params.instructor or params.answers or params.exercises):
        raise UsageError("Specify at least one of: instructor, answers, exercises")

    if os.path.isdir(params.path):
        files = []
        for p in ['*.py', '*.scala', '*.r', '*.sql']:
            files.extend(glob.glob(os.path.join(params.path, p)))
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
        header, commands = parser.generate_commands(db_src, params)
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
    codeGroup.add_argument('-py', '--python',
                           help='generate python notebook(s)',
                           action='store_true')
    codeGroup.add_argument('-r', '--rproject',
                           help='generate r notebook(s)',
                           action='store_true')
    codeGroup.add_argument('-sc', '--scala',
                           help='generate scala notebook(s)',
                           action='store_true')
    codeGroup.add_argument('-sq', '--sql',
                           help='generate sql notebook(s)',
                           action='store_true')

    userGroup = arg_parser.add_argument_group('user')
    userGroup.add_argument('-an', '--answers',
                           help='generate answers notebook(s)',
                           action='store_true')
    userGroup.add_argument('-ex', '--exercises',
                           help='generate exercises notebook(s)',
                           action='store_true')
    userGroup.add_argument('-in', '--instructor',
                           help='generate instructor notebook(s)',
                           action='store_true')

    arg_parser.add_argument('-cc', '--creativecommons',
                            help='add by-nc-nd cc 4.0 license',
                            action='store_true')
    arg_parser.add_argument('--copyright',
                            help='Set the copyright year for any generated ' +
                                 'copyright notices. Default is current year.',
                            default=datetime.now().year,
                            action='store',
                            metavar='YEAR')
    arg_parser.add_argument('-ct', '--course-type',
                            help='Course type, either "ilt" or "self-paced". ' +
                                 'Default: "self-paced"',
                            metavar="<coursetype>",
                            choices=('ilt', 'self-paced'),
                            default='self-paced')
    arg_parser.add_argument('-d', '--dir',
                            help="Base output directory. Default: {0}".format(
                                DEFAULT_OUTPUT_DIR),
                            action='store',
                            dest='output_dir',
                            metavar="OUTPUT_DIR")
    arg_parser.add_argument('-D', '--debug',
                            help="Enable debug messages",
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
    arg_parser.add_argument('--footer',
                            help='By default, even if you specify -nf, this ' +
                                 'tool does not add the notebook footer to ' +
                                 'bottom of generated notebooks. If you ' +
                                 'specify this option, it will do so.',
                            action='store_true')
    arg_parser.add_argument('--heading',
                            help='By default, even if you specify -nh, this ' +
                                 'tool does not add the notebook heading to ' +
                                 'top of generated notebooks. If you specify ' +
                                 'this option, it will do so.',
                            action='store_true')
    arg_parser.add_argument('-nf', '--notebook-footer',
                            help='A file containing Markdown and/or HTML, to ' +
                                 'be used as the bottom-of-notebook footer, ' +
                                 'if headings are enabled. If not specified, ' +
                                 'an internal default (a copyright footer) ' +
                                 'is used. See also --footer and --copyright.',
                            default=None,
                            metavar="<file>")
    arg_parser.add_argument('-nh', '--notebook-heading',
                            help='A file containing Markdown and/or HTML, ' +
                                 'to be used as the top-of-notebook heading, ' +
                                 'if headings are enabled. If not specified, ' +
                                 'an internal default is used. See also ' +
                                 '--heading.',
                            default=None,
                            metavar="<file>")
    arg_parser.add_argument('--templates',
                            help='Enable cell templates. If enabled, each ' +
                                 'cell is run through a Mustache template ' +
                                 'parser, and internal variables (plus ' +
                                 'passed via --variables) are available).',
                            action='store_true')
    arg_parser.add_argument('-tp', '--target-profile',
                            help="Target output profile, if any. Valid " +
                                 "values: amazon, azure",
                            metavar="<profile>",
                            choices=('amazon', 'azure'),
                            default=None)
    arg_parser.add_argument('-v', '--verbose',
                            help="Enable verbose messages.",
                            action='store_true')
    arg_parser.add_argument('--variable',
                            help='Specify an additional variable for the ' +
                                 'cell template processor. Ignored unless ' +
                                 '--template is specified. Can be specified ' +
                                 'multiple times. Format: "var=value", "var", '+
                                 'or "!var". "var=value" defines key "var" ' +
                                 'with string value "value". "var" defines ' +
                                 'key "var" with value True. "!var" defines ' +
                                 'key "var" with value False.',
                            metavar="<var:value>",
                            action='append',
                            default=None)


    args = arg_parser.parse_args()

    if args.version:
        print(VERSION)
        sys.exit(0)

    if (not args.templates) and args.variable:
        print("WARNING: --variable is ignored unless --template is specified.")

    extra_template_vars = None
    if args.templates:
        if args.variable:
            extra_template_vars = {}
            valid_key = re.compile('^[a-zA-Z][a-zA-Z0-9_]*$')
            for s in args.variable:
                kv = s.split('=')
                key = value = None
                length = len(kv)
                if length == 2:
                    key, value = kv
                elif (length == 1):
                    k = kv[0].strip()
                    if len(k) == 0:
                        arg_parser.error('Badly formatted variable: "{}"'.format(kv))
                    elif k[0] == '!':
                        key, value = k[1:], False
                    else:
                        key, value = k, True
                else:
                    arg_parser.error('Badly formatted variable: "{}"'.format(kv))

                if not valid_key.search(key):
                    arg_parser.error('Invalid variable key: {}'.format(key))

                extra_template_vars[key] = value

    if not (args.databricks or args.ipython):
        arg_parser.error('at least one of -db or -ip is required')

    if not (args.scala or args.python or args.rproject or args.sql):
        arg_parser.error('at least one of -sc, -py, -r, or -sq is required')

    if not (args.instructor or args.exercises or args.answers):
        arg_parser.error('at least one of -in, -ex or -an is required')

    if not args.filename:
        arg_parser.error('Missing notebook path.')

    if args.target_profile:
        target_profiles = { t.value : t for t in TargetProfile if t != TargetProfile.NONE }
        args.target_profile = target_profiles[args.target_profile]
    else:
        args.target_profile = TargetProfile.NONE

    course_types = { c.value : c for c in CourseType if c != CourseType.NONE }
    course_type = course_types[args.course_type]

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
        copyright_year=args.copyright,
        target_profile=args.target_profile,
        course_type=course_type,
        enable_templates=args.templates,
        extra_template_vars=extra_template_vars
    )

    try:
        process_notebooks(params)
    except UsageError as e:
        sys.stderr.write(e.message + '\n')
        sys.exit(1)

if __name__ == '__main__':
    main()
