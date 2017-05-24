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

VERSION = "1.2.0"

CommandLabel = Enum('CommandLabel',
                    'IPYTHON_ONLY PYTHON_ONLY SCALA_ONLY ' +
                    'R_ONLY SQL_ONLY ANSWER TODO TEST PRIVATE_TEST ' +
                    'DATABRICKS_ONLY INLINE ALL_NOTEBOOKS INSTRUCTOR_NOTES')
CommandCode = Enum('CommandCode',
                   'SCALA PYTHON R SQL MARKDOWN FILESYSTEM SHELL RUN FS SH')
NotebookKind = Enum('NotebookKind', 'DATABRICKS IPYTHON')
NotebookUser = Enum('NotebookUser', 'INSTRUCTOR STUDENT')
NewlineAfterCode = {CommandCode.SCALA, CommandCode.R, CommandCode.PYTHON}

from collections import namedtuple
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
        NotebookUser.INSTRUCTOR: {CommandLabel.ANSWER,
                                  CommandLabel.INSTRUCTOR_NOTES,
                                  CommandLabel.PRIVATE_TEST},
        NotebookUser.STUDENT: {CommandLabel.TODO},
    }

    user_to_extension = {
        NotebookUser.INSTRUCTOR: '_answers',
        NotebookUser.STUDENT: '_student'
    }

    def __init__(self, notebook_kind, notebook_user, notebook_code):
        base_keep = set(CommandLabel.__members__.values())
        self.keep_labels = self._get_labels(notebook_kind,
                                            notebook_user,
                                            notebook_code)
        # discard labels not explicitly kept
        self.discard_labels = base_keep - self.keep_labels
        self.remove = [_dbc_only, _scala_only, _python_only, _new_part, _inline,
                       _all_notebooks, _instructor_notes]
        self.replace = [(_ipythonReplaceRemoveLine, ''),
                        _rename_public_test,
                        _rename_import_public_test]
        self.notebook_kind = notebook_kind
        self.notebook_user = notebook_user
        self.notebook_code = notebook_code
        self.file_ext = self._get_extension()
        self.base_comment = _code_to_comment[self.notebook_code]

    def _get_labels(self, *params):
        labels = {CommandLabel.TEST, CommandLabel.INLINE}
        for param in params:
            labels.update(NotebookGenerator.param_to_label[param])
        return labels

    def _get_extension(self):
        return (NotebookGenerator.user_to_extension[self.notebook_user] +
                Parser.code_to_extension[self.notebook_code])

    def generate(self, header, commands, input_name, parts=True,
                 creative_commons=False):
        is_IPython = self.notebook_kind == NotebookKind.IPYTHON

        command_cell = _command_cell.format(self.base_comment)

        max_part = max([part for (part, _, _, _) in commands]) if parts else 0
        if max_part == 0 or is_IPython:
            parts = False

        # generate full notebook when generating parts
        if parts:
            self.generate(header, commands, input_name, False,
                          creative_commons=creative_commons)

        base_file = os.path.splitext(os.path.basename(input_name))[0]

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

            with codecs.open(file_out, 'w', _file_encoding_out,
                             errors=_file_encoding_errors) as output:

                # don't write the first # command --- for databricks
                is_first = not is_IPython

                if is_IPython:
                    header_adj = _header
                else:
                    # use proper comment char
                    header_adj = re.sub(_comment, self.base_comment, header)
                    if creative_commons:
                        header_adj += '\n{0} MAGIC %md\n{0} MAGIC {1}'.format(
                            self.base_comment, _cc_license
                        )
                        is_first = False

                output.write(header_adj + '\n')

                added_run = False
                for (part, code, labels, content) in commands:
                    if parts:
                        if part > i:  # don't show later parts
                            break
                        elif part == i - 1 and not added_run:
                            # add %run command before new part
                            student = NotebookGenerator.user_to_extension[
                                NotebookUser.STUDENT
                            ]
                            instr = NotebookGenerator.user_to_extension[
                                NotebookUser.INSTRUCTOR
                            ]
                            solution_file = file_out.replace(student, instr)

                            solution_file = os.path.splitext(solution_file)[0]
                            solution_file = solution_file.replace(
                                part_string, part_base.format(i)
                            )
                            # Now that Databricks supports relative run paths,
                            # this is no longer necessary.
                            #db_location = ('/Users/admin@databricks.com/Labs/' +
                            #               solution_file.replace('\\', '/'))
                            # db_location = db_location.replace('build_mp/', '')
                            db_location = os.path.basename(solution_file.replace('\\', '/'))
                            runCommand = '{0} MAGIC %run {1}'.format(
                                self.base_comment, db_location
                            )
                            is_first = self._write_command(
                                output, command_cell, [runCommand, ''], is_first
                            )
                            added_run = True
                            continue
                        elif part < i:  # earlier parts will be chained in %run
                            continue

                    if (CommandLabel.INSTRUCTOR_NOTES in labels):
                        # Special processing.
                        if code != CommandCode.MARKDOWN:
                            raise Exception(
                                'INSTRUCTOR_NOTES can only appear in Markdown cells.'
                            )
                        content = ['<h2 style="color:red">Instructor Note</h2>'] + content

                    inline = CommandLabel.INLINE in labels
                    all_notebooks = CommandLabel.ALL_NOTEBOOKS in labels
                    discard_labels = self.discard_labels

                    if ((not (discard_labels & labels)) and
                        ((inline and code != self.notebook_code) or
                         (not inline and code == self.notebook_code)) or
                        all_notebooks):

                        content = self.remove_and_replace(content, code, inline,
                                                          all_notebooks, is_first)

                        isCodeCell = code != CommandCode.MARKDOWN

                        cell_split = command_cell
                        if is_IPython:
                            if isCodeCell:
                                cell_split = _code_cell
                            else:
                                cell_split = _markdown_cell

                        is_first = self._write_command(output, cell_split,
                                                       content, is_first)

            if is_IPython:
                self.generate_ipynb(file_out)

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
                if not code in NewlineAfterCode:
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

DEFAULT_ENCODING_IN = 'cp1252'
DEFAULT_ENCODING_OUT = 'utf-8'
DEFAULT_OUTPUT_DIR = 'build_mp'

_file_encoding_in =  DEFAULT_ENCODING_IN
_file_encoding_out = DEFAULT_ENCODING_OUT
_file_encoding_errors = 'strict'
_output_dir = DEFAULT_OUTPUT_DIR


def _collapse(s):
    lines = [line.strip() for line in s.split("\n")]
    non_empty = [line for line in lines if len(line) > 0]
    return ' '.join(non_empty)

# Commons license
_cc_license = _collapse("""
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
""")

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


def make_magic(regex_text):
    # these are without comment chars so allow for spaces
    regex_text = r'\s*' + regex_text + r'(.*)$'
    return re.compile(make_magic_text(regex_text))


_databricks = make_re(r'Databricks')
_command = make_re(r'COMMAND')

_answer = or_magic(r'ANSWER')
_private_test = or_magic(r'PRIVATE_TEST')
_todo = or_magic(r'TODO')
_dbc_only = or_magic(r'DATABRICKS_ONLY')
_ipython_only = or_magic(r'IPYTHON_ONLY')
_python_only = or_magic(r'PYTHON_ONLY')
_scala_only = or_magic(r'SCALA_ONLY')
_sql_only = or_magic(r'SQL_ONLY')
_r_only = or_magic(r'R_ONLY')
_new_part = or_magic(r'NEW_PART')
_inline = or_magic(r'INLINE')
_all_notebooks = or_magic(r'ALL_NOTEBOOKS')
_instructor_notes = or_magic(r'INSTRUCTOR_NOTES')

_ipython_remove_line = re.compile(
    r'.*{0}\s*REMOVE\s*LINE\s*IPYTHON\s*$'.format(_comment)
)

_markdown = make_magic(r'%md')
_scala = make_magic(r'%scala')
_python = make_magic(r'%python')
_r = make_magic(r'%r')
_file_system = make_magic(r'%fs')
_shell = make_magic(r'%sh')
_run = make_magic(r'%run')
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
                        (_instructor_notes, CommandLabel.INSTRUCTOR_NOTES),
                        (_file_system, CommandLabel.ALL_NOTEBOOKS),
                        (_shell, CommandLabel.ALL_NOTEBOOKS),
                        (_sql_only, CommandLabel.SQL_ONLY)]

    pattern_to_code = [(_markdown, CommandCode.MARKDOWN),
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
        self.commands = []
        self.part = 0
        self.header = None
        self.command_code = None

    def _clear_command(self):
        self.command_content = []
        self.command_code = None
        self.command_labels = set()

    def _extend_content(self):
        if self.command_code is None:
            self.command_code = self.base_notebook_code
        else:  # Remove %sql, %fs, etc and MAGIC
            pat = Parser.code_to_pattern[self.command_code]
            self.command_content = _transform_match(self.command_content, [pat])
            self.command_content = _replace_text(self.command_content,
                                                 [_magic_replace])

        if self.command_code not in Parser.master_code:
            # non base notebook commands are inlined automatically
            self.command_labels.add(CommandLabel.INLINE)

        cmd = Command(self.part,
                      self.command_code,
                      self.command_labels,
                      self.command_content)
        self.commands.append(cmd)

    def generate_commands(self, file_name):
        """Generates py file content for DBC and ipynb use.

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
        _, file_extension = os.path.splitext(file_name)
        file_extension = file_extension.lower()

        assert file_extension in Parser.extension_to_code, \
            'Bad file extension for {0}'.format(file_name)
        self.base_notebook_code = Parser.extension_to_code[file_extension]
        base_comment = _code_to_comment[self.base_notebook_code]

        with codecs.open(file_name, 'r', _file_encoding_in,
                         errors=_file_encoding_errors) as dbcExport:
            file_contents = dbcExport.readlines()

        self.commands = []
        self._clear_command()
        self.part = 0

        if len(file_contents) > 0 and _databricks.match(file_contents[0]):
            self.header = file_contents[0]
            # Strip first line if it's the Databricks' timestamp
            file_contents[:1] = []

        for i, line in enumerate(file_contents):

            if _command.match(line):
                if len(self.command_content) > 0:
                    self._extend_content()

                self._clear_command()
                continue

            if _new_part.match(line):
                self.part += 1

            for pat, label in Parser.pattern_to_label:
                if pat.match(line):
                    self.command_labels.add(label)

            for pat, code in Parser.pattern_to_code:
                m = pat.match(line)
                if m:
                    if self.command_code is not None:
                        msg = 'Line "{0}" has multiple magic strings.'.format(
                            line
                        )
                        raise Exception(msg)
                    self.command_code = code

            line = line.rstrip()
            # Lines with only MAGIC do not reimport
            if len(line) <= 8 and line[-5:] == 'MAGIC':
                # Keep empty lines
                self.command_content.append(base_comment + ' MAGIC ')
            else:
                self.command_content.append(line)

        if len(self.command_content) > 0:
            self.command_content.append("")
            self._extend_content()  # EOF reached.  Add the last cell.

        return self.header, self.commands


class UsageError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


def process_notebooks(path,
                      output_dir=DEFAULT_OUTPUT_DIR,
                      databricks=True,
                      ipython=False,
                      scala=False,
                      python=False,
                      r=False,
                      sql=False,
                      instructor=False,
                      student=False,
                      creative_commons=False,
                      encoding_in=DEFAULT_ENCODING_IN,
                      encoding_out=DEFAULT_ENCODING_OUT):
    """
    Main entry point for notebook processing. This function can be used to
    process notebook from within another Python program.

    :param path:               The path to the notebook or to the directory
                               containing the notebooks.
    :param output_dir:         The output directory. Defaults to
                               DEFAULT_OUTPUT_DIR
    :param databricks:         True to include Databricks notebook content,
                               False to suppress it.
    :param ipython:            True to include IPython (Jupyter) notebook
                               content, False to suppress it.
    :param scala:              True to produce Scala notebooks, False to
                               skip all Scala content
    :param python:             True to produce Python notebooks, False to
                               skip all Python content
    :param r:                  True to produce R notebooks, False to skip all
                               R content
    :param sql:                True to produce SQL notebooks, False to skip
                               all SQL content
    :param instructor:         True to produce instructor (answer) notebooks,
                               False otherwise
    :param student:            True to produce student notebooks, False
                               otherwise
    :param creative_commons:   True to add Creative Commons license cells,
                               False otherwise
    :param encoding_in:        Input encoding for the notebook. Defaults to
                               DEFAULT_ENCODING_IN
    :param encoding_out:       Encoding for the output notebook(s). Defaults to
                               DEFAULT_ENCODING_OUT.
    :return: Nothing.
    """
    global _output_dir, _file_encoding_in, _file_encoding_out
    _output_dir = output_dir if output_dir else DEFAULT_OUTPUT_DIR
    _file_encoding_in = encoding_in or DEFAULT_ENCODING_IN
    _file_encoding_out = encoding_out or DEFAULT_ENCODING_OUT

    if not (databricks or ipython):
        raise UsageError("Specify at least one of databricks or ipython")
    if not (scala or python or r or sql):
        raise UsageError("Specify at least one of Scala, Python, R or SQL")
    if not (instructor or student):
        raise UsageError("Specify at least one of instructor or student")

    if os.path.isdir(path):
        files = []
        for p in ['*.py', '*.scala', '*.r', '*.sql']:
            files.extend(glob.glob(os.path.join(path, p)))
    else:
        files = [path]

    if not files:
        raise UsageError("No acceptable files found for {0}".format(path))

    notebook_kinds = []
    if databricks:
        notebook_kinds.append(NotebookKind.DATABRICKS)
    if ipython:
        notebook_kinds.append(NotebookKind.IPYTHON)

    notebook_users = []
    if instructor:
        notebook_users.append(NotebookUser.INSTRUCTOR)
    if student:
        notebook_users.append(NotebookUser.STUDENT)

    notebook_languages = []
    if scala:
        notebook_languages.append(CommandCode.SCALA)
    if python:
        notebook_languages.append(CommandCode.PYTHON)
    if r:
        notebook_languages.append(CommandCode.R)
    if sql:
        notebook_languages.append(CommandCode.SQL)

    if ipython and CommandCode.PYTHON not in notebook_languages:
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
                    notebooks.append(NotebookGenerator(kind, user, lang))

    parser = Parser()
    for db_src in files:
        header, commands = parser.generate_commands(db_src)
        for notebook in notebooks:
            notebook.generate(header, commands, db_src,
                              creative_commons=creative_commons)


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
    userGroup.add_argument('-st', '--student',
                           help='generate student notebook(s)',
                           action='store_true')
    arg_parser.add_argument('-cc', '--creativecommons',
                            help='add by-nc-nd cc 4.0 license',
                            action='store_true')
    arg_parser.add_argument('-ei', '--encoding-in',
                            help="input file encoding",
                            action='store',
                            metavar="ENCODING")
    arg_parser.add_argument('-eo', '--encoding-out',
                            help="output file encoding",
                            action='store',
                            metavar="ENCODING")
    arg_parser.add_argument('-d', '--dir',
                            help="Base output directory. Default: {0}".format(
                                DEFAULT_OUTPUT_DIR),
                            action='store',
                            dest='output_dir',
                            metavar="OUTPUT_DIR")

    args = arg_parser.parse_args()

    if args.version:
        print('Master Parse tool, version {0}'.format(VERSION))
        sys.exit(0)

    if not (args.databricks or args.ipython):
        arg_parser.error('at least one of -db or -ip is required')

    if not (args.scala or args.python or args.rproject or args.sql):
        arg_parser.error('at least one of -sc, -py, -r, or -sq is required')

    if not (args.instructor or args.student):
        arg_parser.error('at least one of -in or -st is required')

    try:
        process_notebooks(path=args.filename,
                          output_dir=args.output_dir,
                          databricks=args.databricks,
                          ipython=args.ipython,
                          scala=args.scala,
                          python=args.python,
                          r=args.rproject,
                          sql=args.sql,
                          instructor=args.instructor,
                          student=args.student,
                          creative_commons=args.creativecommons,
                          encoding_in=args.encoding_in,
                          encoding_out=args.encoding_out)
    except UsageError as e:
        sys.stderr.write(e.message + '\n')
        sys.exit(1)

if __name__ == '__main__':
    main()
