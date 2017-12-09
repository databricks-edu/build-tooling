#!/usr/bin/env python

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from builtins import (bytes, dict, int, list, object, range, str, ascii,
                      chr, hex, input, next, oct, open, pow, round, super,
                      filter, map, zip)

from future import standard_library
standard_library.install_aliases()

import sys

if sys.version_info[0] != 2:
    print("bdc only works on Python 2. You're using Python {0}.".format(
        '.'.join([str(i) for i in sys.version_info[0:3]])
    ))
    sys.exit(1)

import subprocess
import json

from collections import namedtuple
import os
from os import path
from string import Template
import codecs
import re
from datetime import datetime
from ConfigParser import SafeConfigParser, NoOptionError
from enum import Enum
import master_parse
from grizzled.file import eglob
from bdc.bdcutil import (merge_dicts, bool_value, bool_field, DefaultStrMixin,
                         variable_ref_patterns, matches_variable_ref,
                         working_directory, move, copy, mkdirp, markdown_to_html,
                         warning, info, emit_error, verbose, set_verbosity,
                         verbosity_is_enabled, ensure_parent_dir_exists,
                         parse_version_string, find_in_path, rm_rf, joinpath,
                         dict_get_and_del)

# We're using backports.tempfile, instead of tempfile, so we can use
# TemporaryDirectory in both Python 3 and Python 2. tempfile.TemporaryDirectory
# was added in Python 3.2.
from backports.tempfile import TemporaryDirectory

# ---------------------------------------------------------------------------
# Constants
#
# (Some constants are below the class definitions.)
# ---------------------------------------------------------------------------

VERSION = "1.12.0"

DEFAULT_BUILD_FILE = 'build.yaml'
PROG = os.path.basename(sys.argv[0])

DB_SHARD_HOME_VAR = 'DB_SHARD_HOME'

USAGE = ("""
{0}, version {1}

Usage:
  {0} (--version)
  {0} (-h | --help)
  {0} [-o | --overwrite] [-v | --verbose] [-d DEST | --dest DEST] [BUILD_YAML] 
  {0} --list-notebooks [BUILD_YAML]
  {0} --upload [-v | --verbose] SHARD_FOLDER_PATH [BUILD_YAML]
  {0} --download [-v | --verbose] SHARD_FOLDER_PATH [BUILD_YAML]

MASTER_CFG is the build tool's master configuration file.

BUILD_YAML is the build file for the course to be built. Defaults to {2}.

SHARD_FOLDER_PATH is the path to a folder on a Databricks shard, as supported
by the Databricks CLI. You must install databricks-cli and configure it
properly for --upload and --download to work.

Options:
  -h --help            Show this screen.
  -d DEST --dest DEST  Specify output destination. Defaults to
                       ~/tmp/curriculum/<course_id>
  -o --overwrite       Overwrite the destination directory, if it exists.
  -v --verbose         Print what's going on to standard output.
  --list-notebooks     List the full paths of all notebooks in a course
  --upload             Upload all notebooks to a folder on Databricks.
  --download           Download all notebooks from a folder on Databricks,
                       copying them into their appropriate locations on the 
                       local file system, as defined in the build.yaml file.
  --version            Display version and exit.

""".format(PROG, VERSION, DEFAULT_BUILD_FILE))

DEFAULT_INSTRUCTOR_FILES_SUBDIR = "InstructorFiles"
INSTRUCTOR_LABS_SUBDIR = "Instructor-Labs"
INSTRUCTOR_LABS_DBC = "Instructor-Labs.dbc"
DEFAULT_STUDENT_FILES_SUBDIR = "StudentFiles"
STUDENT_LABS_DBC = "Labs.dbc"               # in the student directory
STUDENT_LABS_SUBDIR = "Labs"                # in the student directory
SLIDES_SUBDIR = "Slides"                    # in the instructor directory
DATASETS_SUBDIR = "Datasets"                # in the student directory
INSTRUCTOR_NOTES_SUBDIR = "InstructorNotes" # in the instructor directory

# Post master-parse variables (and associated regexps)
TARGET_LANG = 'target_lang'
TARGET_EXTENSION = 'target_extension'
NOTEBOOK_TYPE = 'notebook_type'

POST_MASTER_PARSE_VARIABLES = {
    TARGET_LANG:         variable_ref_patterns(TARGET_LANG),
    TARGET_EXTENSION:    variable_ref_patterns(TARGET_EXTENSION),
    NOTEBOOK_TYPE:       variable_ref_patterns(NOTEBOOK_TYPE),
}

# EXT_LANG is used when parsing the YAML file.
EXT_LANG = {'.py':    'Python',
            '.r':     'R',
            '.scala': 'Scala',
            '.sql':   'SQL'}

# LANG_EXT: Mapping of language (in lower case) to extension
LANG_EXT = dict([(v.lower(), k) for k, v in EXT_LANG.items()])

# Used to create a Scala version notebook in the top-level. This is a string
# template, with the following variables:
#
# {course_name}     - the course name
# {version}         - the version
# {build_timestamp} - the build timestamp, in printable format
VERSION_NOTEBOOK_TEMPLATE = """// Databricks notebook source

// MAGIC %md # Course: ${course_name}
// MAGIC <br/>
// MAGIC * Version ${version}
// MAGIC * Built ${build_timestamp}
// MAGIC
// MAGIC Copyright \u00a9 ${year} Databricks, Inc.
"""

# The version notebook file name. Use as a format string, with {0} as the
# version number.
VERSION_NOTEBOOK_FILE = "Version-{0}.scala"

ANSWERS_NOTEBOOK_PATTERN = re.compile('^.*_answers\..*$')

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

errors = 0

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class BuildError(Exception):
    pass


class UploadDownloadError(Exception):
    pass


class ConfigError(BuildError):
    pass


class UnknownFieldsError(ConfigError):
    def __init__(self, parent_section, section_name, unknown_keys):
        super(ConfigError, self).__init__(
            '"{0}": Unknown fields in "{1}" section: {2}'.format(
                parent_section, section_name, ', '.join(unknown_keys)
            )
        )

class NotebookType(Enum):
    EXERCISES = 'exercises'
    INSTRUCTOR = 'instructor'
    ANSWERS = 'answers'

    @classmethod
    def default_mappings(cls):
        return {
            NotebookType.EXERCISES:  'exercises',
            NotebookType.INSTRUCTOR: 'instructor',
            NotebookType.ANSWERS:    'answers',
        }

    def suffix_for(self):
        '''
        Get the filename suffix for the notebook type (e.g., '_exercises').

        :return: the suffix
        '''
        return NotebookType.suffixes()[self]

    @classmethod
    def suffixes(cls):
        '''
        Get a dict of NotebookType -> suffix mappings

        :return: the mappings
        '''
        return {
            NotebookType.EXERCISES:  '_exercises',
            NotebookType.INSTRUCTOR: '_instructor',
            NotebookType.ANSWERS:    '_answers',
        }

    def __repr__(self):
        return 'NotebookType.{0}'.format(self.name)


MiscFileData = namedtuple('MiscFileData', ('src', 'dest'))
SlideData = namedtuple('SlideData', ('src', 'dest'))
DatasetData = namedtuple('DatasetData', ('src', 'dest', 'license', 'readme'))
CourseInfo = namedtuple('CourseInfo', ('name', 'version', 'class_setup',
                                       'schedule', 'instructor_prep',
                                       'copyright_year', 'deprecated'))
MarkdownInfo = namedtuple('MarkdownInfo', ('html_stylesheet',))
NotebookHeading = namedtuple('NotebookHeading', ('path', 'enabled'))
NotebookFooter = namedtuple('NotebookFooter', ('path', 'enabled'))

class NotebookDefaults(object, DefaultStrMixin):
    def __init__(self, dest=None, master=None):
        '''
        Create a new NotebookDefaults object.

        :param dest:    The destination value (str)
        :param master:  The master parse section (dict, not MasterParseInfo)
        '''
        self.dest = dest
        self.master = master or {}


class MasterParseInfo(object, DefaultStrMixin):
    LANGUAGES = ('python', 'scala', 'r', 'sql')

    VALID_FIELDS = {
        'enabled': bool,
        'python': bool,
        'scala': bool,
        'r': bool,
        'sql': bool,
        'answers': bool,
        'exercises': bool,
        'instructor': bool,
        'heading': NotebookHeading.__class__,
        'footer': NotebookFooter.__class__,
        'encoding_in': str,
        'encoding_out': str
    }

    VALID_HEADING_FIELDS = {
        'path': str,
        'enabled': bool
    }

    VALID_FOOTER_FIELDS = {
        'path': str,
        'enabled': bool
    }

    '''
    Parsed master parser data for a notebook.
    '''
    def __init__(self,
                 enabled=False,
                 python=True,
                 scala=True,
                 r=False,
                 sql=False,
                 answers=True,
                 exercises=True,
                 instructor=True,
                 heading=NotebookHeading(path=None, enabled=True),
                 footer=NotebookFooter(path=None, enabled=True),
                 encoding_in='UTF-8',
                 encoding_out='UTF-8'):
        '''
        Create a new parsed master parse data object

        :param enabled:      whether master parsing is enabled for the notebook
        :param python:       whether Python notebook generation is enabled
        :param scala:        whether Scala notebook generation is enabled
        :param r:            whether R notebook generation is enabled
        :param sql:          whether SQL notebook generation is enabled
        :param answers:      whether to generate answer notebooks
        :param exercises:    whether to generate exercises notebook
        :param instructor:   whether to generate instructor notebooks
        :param heading:      heading information (a NotebookHeading object)
        :param footer:       footer information (a NotebookFooter object)
        :param encoding_in:  the encoding of the source notebooks
        :param encoding_out: the encoding to use when writing notebooks
        '''
        self.enabled      = enabled
        self.python       = python
        self.scala        = scala
        self.r            = r
        self.sql          = sql
        self.answers      = answers
        self.exercises    = exercises
        self.instructor   = instructor
        self.heading      = heading
        self.footer       = footer
        self.encoding_in  = encoding_in
        self.encoding_out = encoding_out

    def lang_is_enabled(self, lang):
        '''
        Determine if a specific language is enabled.

        :param lang:  the name (string) for the language, in lower case

        :return: True if it's enable, False if not
        '''
        return self.__getattribute__(lang)

    def enabled_langs(self):
        '''
        Return a list of the enabled languages. e.g., ['scala', 'python']

        :return: the list of enabled languages, which could be empty
        '''
        return [i for i in self.LANGUAGES if self.__getattribute__(i)]

    def update_from_dict(self, d):
        '''
        Update the fields in this master parse record from a dictionary.
        The dictionary should represent a master parse dictionary (e.g., as
        parsed from YAML). Keys can be missing. Extra keys are ignored.

        :param d: the dictionary
        '''
        for k in self.VALID_FIELDS.keys():
            if k in d:
                if k == 'heading':
                    heading_data = d[k]
                    if isinstance(heading_data, NotebookHeading):
                        self.heading = heading_data
                    else:
                        self.heading = self._parse_heading(d[k])
                elif k == 'footer':
                    footer_data = d[k]
                    if isinstance(footer_data, NotebookFooter):
                        self.footer = footer_data
                    else:
                        self.footer = self._parse_footer(d[k])

                else:
                    self.__setattr__(k, d[k])

    @classmethod
    def extra_keys(cls, d):
        '''
        Check a dictionary of master parse value for extra (unknown) keys.

        :param d: the dictionary to check

        :return: any unknown keys, or None if there aren't any.
        '''
        extra = set(d.keys()) - set(cls.VALID_FIELDS.keys())
        heading = d.get('heading', {})
        for k in (set(heading.keys()) - set(cls.VALID_HEADING_FIELDS.keys())):
            extra.add('heading.{0}'.format(k))

        if len(extra) == 0:
            extra = None

        return extra

    @classmethod
    def from_dict(cls, d):
        '''
        Create a MasterParseData object from a dictionary of values.

        :param d: the dictionary.

        :return: The object. Throws exceptions on error. Extra keys are not
                 interpreted as an error here; callers can report those errors
                 with more context.
        '''
        heading = cls._parse_heading_data(d.get('heading'))

        return MasterParseInfo(
            enabled=bool_field(d, 'enabled', False),
            python=bool_field(d, 'python', True),
            scala=bool_field(d, 'scala', True),
            r=bool_field(d, 'r', True),
            sql=bool_field(d, 'sql', False),
            answers=bool_field(d, 'answers', True),
            exercises=bool_field(d, 'exercises', True),
            instructor=bool_field(d, 'instructor', True),
            heading=heading,
            encoding_in=d.get('encoding_in', 'UTF-8'),
            encoding_out=d.get('encoding_out', 'UTF-8')
        )

    def to_dict(self):
        '''
        Convert this object into a dictionary.

        :return: the dictionary of fields
        '''
        res = {}
        res.update(self.__dict__)
        return res

    @classmethod
    def _parse_footer(cls, footer_data):
        if footer_data:
            heading = NotebookFooter(
                path=footer_data.get('path', DEFAULT_NOTEBOOK_FOOTER.path),
                enabled=bool_field(footer_data, 'enabled',
                                   DEFAULT_NOTEBOOK_FOOTER.enabled)
            )
        else:
            heading = NotebookHeading(path=None, enabled=True)

        return heading

    @classmethod
    def _parse_heading(cls, heading_data):
        if heading_data:
            heading = NotebookHeading(
                path=heading_data.get('path', DEFAULT_NOTEBOOK_HEADING.path),
                enabled=bool_field(heading_data, 'enabled',
                                   DEFAULT_NOTEBOOK_HEADING.enabled)
            )
        else:
            heading = NotebookHeading(path=None, enabled=True)

        return heading


class NotebookData(object, DefaultStrMixin):
    '''
    Parsed notebook data.
    '''
    def __init__(self,
                 src,
                 dest,
                 upload_download=True,
                 master=None,
                 notebook_defaults=None):
        super(NotebookData, self).__init__()
        self.src = src
        self.dest = dest
        if master:
            self.master = master
        else:
            self.master = merge_dicts(MASTER_PARSE_DEFAULTS,
                                      notebook_defaults.get('master', {}))
        self.notebook_defaults = notebook_defaults
        self.upload_download = upload_download

    def master_enabled(self):
        '''
        Determine whether master notebook processing is enabled for this
        notebook.

        :return: true or false
        '''
        return self.master.enabled

    def total_master_langs(self):
        '''
        Get the number of output languages produced by the master parser
        for this notebook.

        :return: 0 if the master parser isn't enabled. Number of output
                 languages otherwise.
        '''
        return len(self.master.enabled_langs()) if self.master.enabled else 0

    def master_multiple_langs(self):
        '''
        Determine whether the master parser is parsing to multiple languages
        or not.

        :return: True if master parsing is enabled and parsing to multiple
                 languages; False if master parsing is disabled or is enabled
                 but with only one output language.
        '''
        return self.total_master_langs() > 0


class BuildData(object, DefaultStrMixin):
    '''
    Parsed build data.
    '''
    def __init__(self,
                 build_file_path,
                 top_dbc_folder_name,
                 source_base,
                 student_dir,
                 instructor_dir,
                 course_info,
                 notebooks,
                 slides,
                 datasets,
                 misc_files,
                 keep_lab_dirs,
                 markdown_cfg,
                 notebook_type_map,
                 variables=None):
        '''
        Create a new BuildData object.

        :param build_file_path:       path to the build file, for reference
        :param top_dbc_folder_name:   top-level directory in DBC, or None
        :param source_base:           value of source base field
        :param course_info:           parsed CourseInfo object
        :param notebooks:             list of parsed Notebook objects
        :param slides:                parsed SlideInfo object
        :param datasets:              parsed DatasetData object
        :param misc_files:            parsed MiscFilesData object
        :param keep_lab_dirs:         value of keep_lab_dirs setting
        :param notebook_heading:      parsed NotebookHeading object
        :param markdown_cfg:          parsed MarkdownInfo object
        :param notebook_type_map:     a dict mapping notebook types to strings.
                                      Keys are from the NotebookType enum.
        :param variables:             a map of user-defined variables
        '''
        super(BuildData, self).__init__()
        self.build_file_path = build_file_path
        self.course_directory = path.dirname(build_file_path)
        self.notebooks = notebooks
        self.course_info = course_info
        self.source_base = source_base
        self.student_dir = student_dir
        self.instructor_dir = instructor_dir
        self.slides = slides
        self.datasets = datasets
        self.markdown = markdown_cfg
        self.misc_files = misc_files
        self.keep_lab_dirs = keep_lab_dirs
        self.notebook_type_map = notebook_type_map
        self.variables = variables or {}

        if top_dbc_folder_name is None:
            top_dbc_folder_name = '${course_name}'

        folder_vars = dict(variables)
        folder_vars.update({
            'course_name':    course_info.name,
            'course_version': course_info.version,
            'course_id':      self.course_id,
        })

        self.top_dbc_folder_name = Template(top_dbc_folder_name).substitute(
            folder_vars
        )

    @property
    def name(self):
        return self.course_info.name

    @property
    def course_id(self):
        '''
        The course ID, which is a combination of the course name and the
        version.

        :return: the course ID string
        '''
        return '{0}-{1}'.format(self.name, self.course_info.version)

# ---------------------------------------------------------------------------
# Class-dependent Constants
# ---------------------------------------------------------------------------

DEFAULT_NOTEBOOK_FOOTER = NotebookFooter(path=None, enabled=True)
DEFAULT_NOTEBOOK_HEADING = NotebookHeading(path=None, enabled=True)

# Always generate Databricks notebooks.
MASTER_PARSE_DEFAULTS = {
    'enabled':          False,
    'add_heading':      True,
    'python':           True,
    'r':                False,
    'scala':            True,
    'sql':              False,
    'answers':          True,
    'instructor':       True,
    'encoding_in':      'UTF-8',
    'encoding_out':     'UTF-8',
    'heading':          DEFAULT_NOTEBOOK_HEADING,
    'footer':           DEFAULT_NOTEBOOK_FOOTER,
}

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def error(msg):
    global errors
    errors += 1
    emit_error(msg)


def die(msg, show_usage=False):
    """
    Emit a message to standard error, optionally write the usage, and exit.
    """
    error(msg)
    if show_usage:
        sys.stderr.write(USAGE)
    sys.stderr.write("\n*** ABORTED\n")
    sys.exit(1)


def load_build_yaml(yaml_file):
    """
    Load the YAML configuration file that defines the build for a particular
    class. Returns a BuildData object. Throws ConfigError on error.

    :param yaml_file  the path to the build file to be parsed

    :return the Build object, representing the parsed build.yaml
    """
    import yaml

    def required(d, key, where, error=None):
        '''
        Get a required key

        :param d:      the dictionary
        :param key:    the key
        :param where:  where in the file the key should be (for errors)
        :param error:  error message, or None for default
        :return:
        '''
        v = d.get(key)
        if v is None:
            if error:
                msg = error
            else:
                msg = 'Missing required "{0}" in "{1}".'.format(key, where)

            raise ConfigError(msg)

        return v

    def subst(dest, src, allow_lang=True, extra_vars=None):
        # Handles parse-time variable substitution. Some variables are
        # substituted later.
        if extra_vars is None:
            extra_vars = {}
        base_with_ext = path.basename(src)
        (base_no_ext, ext) = path.splitext(base_with_ext)

        if '@' in dest:
            raise ConfigError('The "@" character is disallowed in destinations.')

        # A set of variables is expanded only after master parsing; all others
        # are expanded here. Any references to post master-parse variables
        # (expanded in process_master_notebook) must be explicitly preserved
        # here. This logic escapes them by removing the "$" and surrounding the
        # rest with @ ... @. The escaping is undone, below.

        adj_dest = dest
        subbed = True
        while subbed:
            subbed = False
            for pats in POST_MASTER_PARSE_VARIABLES.values():
                m = matches_variable_ref(pats, adj_dest)
                if m:
                    var = '@{0}@'.format(m[1].replace(r'$', ''))
                    adj_dest = m[0] + var + m[2]
                    subbed = True

        fields = {
            'basename':        base_no_ext,
            'extension':       ext[1:] if ext.startswith('') else ext,
            'filename':        base_with_ext,
        }
        if allow_lang:
            fields['lang'] = EXT_LANG.get(ext, "???")

        fields.update(extra_vars)

        # Restore escaped variables.
        adj_dest = Template(adj_dest).substitute(fields)
        escaped = re.compile(r'^([^@]*)@([^@]+)@(.*)$')
        m = escaped.match(adj_dest)
        while m:
            adj_dest = m.group(1) + '$' + m.group(2) + m.group(3)
            m = escaped.match(adj_dest)

        return adj_dest

    def parse_dict(d, fields_spec, outer_section, section):
        res = {}
        for field, type in fields_spec.items():
            if field not in d:
                continue
            if type is bool:
                try:
                    res[field] = bool_value(d[field])
                except ValueError as e:
                    raise ConfigError(
                        '{0}: Bad value for "{1}" in section "{2}": {3}'.format(
                            outer_section, field, section, e.message
                        )
                    )
                continue
            # Anything else gets copied as is for now.
            res[field] = d[field]

        return res

    def parse_master_section(data, section_name):
        # Parse the master section, returning a (possibly partial)
        # dictionary (NOT a MasterParseInfo object).
        extra_keys = MasterParseInfo.extra_keys(data)
        if extra_keys:
            raise UnknownFieldsError(section_name, "master", extra_keys)

        master = parse_dict(data, MasterParseInfo.VALID_FIELDS,
                            section_name, 'master')
        heading = master.get('heading')
        if heading:
            heading = parse_dict(heading, MasterParseInfo.VALID_HEADING_FIELDS,
                                 section_name, 'master.heading')
            if heading.get('path') == 'DEFAULT':
                heading['path'] = None
            master['heading'] = heading

        footer = master.get('footer')
        if footer:
            footer = parse_dict(footer, MasterParseInfo.VALID_FOOTER_FIELDS,
                                section_name, 'master.footer')
            if footer.get('path') == 'DEFAULT':
                footer['path'] = None
            master['footer'] = footer

        return master

    def parse_notebook_defaults(contents, section_name):
        cfg = contents.get(section_name)
        if not cfg:
            return NotebookDefaults(dest=None, master=None)

        master = parse_master_section(dict_get_and_del(cfg, 'master', {}),
                                      'notebook_defaults')
        res = NotebookDefaults(dest=dict_get_and_del(cfg, 'dest', None),
                               master=master)

        if len(cfg.keys()) > 0:
            raise UnknownFieldsError("build", section_name, cfg.keys())

        return res

    def parse_notebook(obj, notebook_defaults, extra_vars):
        bad_dest = re.compile('^\.\./*|^\./*')
        src = required(obj, 'src', 'notebooks section')
        section = 'Notebook "{0}"'.format(src)

        dest = obj.get('dest', notebook_defaults.dest)
        if not dest:
            raise ConfigError(
                ('Notebook "{0}": Missing "dest" section, and no default ' +
                 '"dest" in notebook defaults.').format(src)
            )

        dest = subst(dest, src, extra_vars=extra_vars)
        if bool_field(obj, 'skip'):
            verbose('Skipping notebook {0}'.format(src))
            return None

        master = MasterParseInfo() # defaults
        master.update_from_dict(notebook_defaults.master)
        nb_master = parse_master_section(obj.get('master', {}), section)
        master.update_from_dict(nb_master)

        _, dest_ext = os.path.splitext(dest)
        if master.enabled and bad_dest.match(dest):
            raise ConfigError(
                ('Notebook "{0}": Relative destinations ("{1}") are ' +
                 'disallowed.').format(src, dest)
            )

        if master.enabled:
            total_langs = len(master.enabled_langs())
            if (total_langs > 1):
                pat = POST_MASTER_PARSE_VARIABLES[TARGET_LANG]
                if not matches_variable_ref(pat, dest):
                    raise ConfigError(
                        ('Notebook "{0}": When multiple master parser languages ' +
                         'are used, you must substitute ${1} in the ' +
                         'destination.').format(
                            src, TARGET_LANG, TARGET_EXTENSION
                        )
                    )
        else:
            _, src_ext = os.path.splitext(src)
            if (not dest_ext) or (dest_ext != src_ext):
                raise ConfigError(
                    ('Notebook "{0}": "master" is disabled, so "dest" should ' +
                     'have extension "{1}".').format(src, src_ext)
                )
            for pats in POST_MASTER_PARSE_VARIABLES.values():
                m = matches_variable_ref(pats, dest)
                if m:
                    raise ConfigError(
                      ('Notebook "{0}": "{1}" found in "dest", but "master" ' +
                       'is disabled.').format(src, m[1])
                )

        nb = NotebookData(
            src=src,
            dest=dest,
            master=master,
            upload_download=bool_field(obj, 'upload_download', True)
        )

        return nb

    def parse_slide(obj, extra_vars):
        src = required(obj, 'src', 'notebooks')
        dest = required(obj, 'dest', 'notebooks')
        if bool_field(obj, 'skip'):
            verbose('Skipping slide {0}'.format(src))
            return None
        else:
            return SlideData(
                src=src,
                dest=subst(dest, src, allow_lang=False, extra_vars=extra_vars)
            )

    def parse_misc_file(obj, extra_vars):
        src = required(obj, 'src', 'misc_files')
        dest = required(obj, 'dest', 'misc_files')
        if bool_field(obj, 'skip'):
            verbose('Skipping file {0}'.format(src))
            return None
        else:
            return MiscFileData(
                src=src,
                dest=subst(dest, src, allow_lang=False, extra_vars=extra_vars)
            )

    def parse_dataset(obj, extra_vars):
        src = required(obj, 'src', 'notebooks')
        dest = required(obj, 'dest', 'notebooks')
        if bool_field(obj, 'skip'):
            verbose('Skipping data set {0}'.format(src))
            return None
        else:
            src_dir = path.dirname(src)
            return DatasetData(
                src=src,
                dest=subst(dest, src, allow_lang=False, extra_vars=extra_vars),
                license=joinpath(src_dir, 'LICENSE.md'),
                readme=joinpath(src_dir, 'README.md')
            )

    def parse_file_section(section, parse, *args):
        # Use the supplied parse function to parse each element in the
        # supplied section, filtering out None results from the function.
        # Convert the entire result to a tuple.
        return tuple(
            filter(lambda o: o != None, [parse(i, *args) for i in section])
        )

    def parse_markdown(obj):
        if obj:
            stylesheet = obj.get('html_stylesheet')
        else:
            stylesheet = None
        return MarkdownInfo(html_stylesheet=stylesheet)

    def parse_notebook_types(contents):
        res = NotebookType.default_mappings()
        names_to_keys = dict([(t.value, t) for t in NotebookType])

        invalid_keys = set()
        for k, v in contents.get('notebook_type_name', {}).items():
            t = names_to_keys.get(k)
            if not t:
                invalid_keys.add(k)
            else:
                res[t] = v

        if invalid_keys:
            raise ConfigError(
                'Unknown key(s) in "notebook_type_name" section: {0}'.format(
                    ', '.join(invalid_keys)
                ))
        return res

    def parse_min_version(key, value):
        res = contents.get(key)
        if res is not None:
            if isinstance(res, float):
                raise ConfigError(
                    '"{0}" of the form <major>.<minor> must be quoted.'.format(
                        key
                    )
                )
            try:
                # Ignore the match version.
                res = parse_version_string(res)[0:2]
            except ValueError as e:
                raise ConfigError(
                    'Bad value of "{0}" for "{1}": {2}'.format(
                        res, key, e.message
                    )
                )
        return res

    # Main function logic

    verbose("Loading {0}...".format(yaml_file))
    with open(yaml_file, 'r') as y:
        contents = yaml.safe_load(y)

    bdc_min_version = parse_min_version(
       'bdc_min_version', required(contents, 'bdc_min_version', 'build')
    )

    cur_major_minor = parse_version_string(VERSION)[0:2]
    if bdc_min_version > cur_major_minor:
        raise ConfigError(
            ("This build requires bdc version {0}.x or greater, but " +
             "you're using bdc version {1}.").format(
                '.'.join(map(str, bdc_min_version)), VERSION
            )
        )

    variables = contents.get('variables', {})
    notebooks_cfg = required(contents, 'notebooks', 'build')
    slides_cfg = contents.get('slides', [])
    misc_files_cfg = contents.get('misc_files', [])
    datasets_cfg = contents.get('datasets', [])
    course_info_cfg = required(contents, 'course_info', 'build')
    course_info = CourseInfo(
        name=required(course_info_cfg, 'name', 'course_info'),
        version=required(course_info_cfg, 'version', 'course_info'),
        class_setup=course_info_cfg.get('class_setup'),
        schedule=course_info_cfg.get('schedule'),
        instructor_prep=course_info_cfg.get('prep'),
        deprecated=course_info_cfg.get('deprecated', False),
        copyright_year=course_info_cfg.get('copyright_year',
                                           str(datetime.now().year)),
    )

    src_base = required(contents, 'src_base', 'build')
    build_yaml_full = path.abspath(yaml_file)
    build_yaml_dir = path.dirname(build_yaml_full)
    src_base = path.abspath(joinpath(build_yaml_dir, src_base))

    notebook_defaults = parse_notebook_defaults(contents, 'notebook_defaults')

    if slides_cfg:
        slides = parse_file_section(slides_cfg, parse_slide, variables)
    else:
        slides = None

    if datasets_cfg:
        datasets = parse_file_section(datasets_cfg, parse_dataset, variables)
    else:
        datasets = None

    if misc_files_cfg:
        misc_files = parse_file_section(misc_files_cfg, parse_misc_file,
                                        variables)
    else:
        misc_files = None

    if notebooks_cfg:
        notebooks = parse_file_section(notebooks_cfg, parse_notebook,
                                       notebook_defaults, variables)
    else:
        notebooks = None

    need_master = any([n.master.enabled for n in notebooks])
    if need_master:
        required_master_min_version = parse_min_version(
            'master_parse_min_version',
            required(contents,'master_parse_min_version', 'build',
                     error='"master_parse_min_version" is required if any ' +
                           'notebooks use the master parser.')
        )

        master_version = parse_version_string(master_parse.VERSION)[0:2]
        if required_master_min_version > master_version:
            raise ConfigError(
                ("This build requires master_parse version {0}.x or greater, " +
                 "but you're using master_parse version {1}.").format(
                     '.'.join(map(str, required_master_min_version)),
                     master_parse.VERSION
                )
            )

    student_dir = contents.get('student_dir', DEFAULT_STUDENT_FILES_SUBDIR)
    instructor_dir = contents.get('instructor_dir',
                                  DEFAULT_INSTRUCTOR_FILES_SUBDIR)

    if student_dir == instructor_dir:
        raise ConfigError(
            ('"student_dir" and "instructor_dir" cannot be the same. ' +
             '"student_dir" is "{0}". ' +
             '"instructor_dir" is "{1}".').format(student_dir, instructor_dir)
        )

    data = BuildData(
        build_file_path=build_yaml_full,
        top_dbc_folder_name=contents.get('top_dbc_folder_name'),
        course_info=course_info,
        notebooks=notebooks,
        slides=slides,
        datasets=datasets,
        source_base=src_base,
        student_dir=student_dir,
        instructor_dir=instructor_dir,
        misc_files=misc_files,
        keep_lab_dirs=bool_field(contents, 'keep_lab_dirs'),
        markdown_cfg=parse_markdown(contents.get('markdown')),
        notebook_type_map=parse_notebook_types(contents),
        variables=variables
    )

    return data


def parse_args():
    """
    Parse the command line parameters.
    """
    from docopt import docopt
    return docopt(USAGE, version=VERSION)


def copy_info_file(src_file, target_file, build):
    """
    Copy a file that contains some kind of readable information (e.g., a
    Markdown file, a PDF, etc.). If the file is a Markdown file, it is also
    converted to HTML and copied.
    """
    copy(src_file, target_file)
    src_base = path.basename(src_file)
    (src_simple, ext) = path.splitext(src_base)
    if (ext == '.md') or (ext == '.markdown'):
        target_full = path.abspath(target_file)
        html_out = joinpath(path.dirname(target_full),
                                src_simple + '.html')
        markdown_to_html(
            markdown=src_file,
            html_out=html_out,
            html_template=None,
            stylesheet=build.markdown.html_stylesheet)


def process_master_notebook(dest_root, notebook, src_path, build):
    """
    Process a master notebook.

    :param dest_root:             top-level target directory for build
    :param notebook:              the notebook data from the build YAML
    :param src_path:              the pre-calculated path to the source notebook
    :param dest_path:             the path to the target directory, calculated
                                  from dest_root and notebook.dest
    :param build                  parsed build data

    :return: None
    """
    verbose("notebook={0}\ndest_root={1}".format(notebook, dest_root))
    notebook_type_map = build.notebook_type_map
    student_labs_subdir = joinpath(build.student_dir, STUDENT_LABS_SUBDIR)
    instructor_labs_subdir = joinpath(build.instructor_dir,
                                      INSTRUCTOR_LABS_SUBDIR)
    student_dir = joinpath(dest_root, student_labs_subdir)
    instructor_dir = joinpath(dest_root, instructor_labs_subdir)

    def move_master_notebooks(master, temp_output_dir):
        """
        Move master-parsed notebooks.

        :param master:           the master notebook configuration data
        :param temp_output_dir:  the temporary output directory
        """
        # See if we have to move the notebooks to other paths.
        for lang in set(EXT_LANG.values()):
            lc_lang = lang.lower()
            if not master.lang_is_enabled(lc_lang):
                continue

            # This language is desired.

            # Get the file name extension for the language. Note that this
            # extension INCLUDES the ".".
            lang_ext = LANG_EXT[lc_lang]

            # The master parse tool created <notebook-basename>/<lang>/*
            # in the temporary directory. The following recursive glob pattern
            # will make finding the files simple. In this glob pattern, {0} is
            # the notebook type (e.g., "_answers"), and {1} is the file
            # extension (e.g., ".py")
            glob_template = "**/*{0}*{1}"

            # Copy all answers notebooks and exercises notebooks to the student
            # labs directory. Copy all instructor notebooks to the instructor
            # labs directory.

            types_and_targets = []

            if master.exercises:
                types_and_targets.append(
                    (NotebookType.EXERCISES, student_dir)
                )

            if master.instructor:
                types_and_targets.append(
                  (NotebookType.INSTRUCTOR, instructor_dir)
                )

            if master.answers:
                types_and_targets.append((NotebookType.ANSWERS, student_dir))

            base, _ = path.splitext(path.basename(notebook.src))
            mp_notebook_dir = joinpath(temp_output_dir, base, lc_lang)

            lang_dir = lc_lang.capitalize()
            for notebook_type, target_dir in types_and_targets:
                # Use a recursive glob pattern to find all matching notebooks.
                # Note that eglob returns a generator.
                copied = 0
                suffix = NotebookType.suffix_for(notebook_type)
                glob_pattern = glob_template.format(suffix, lang_ext)
                matches = eglob(glob_pattern, mp_notebook_dir)
                ext = LANG_EXT[lc_lang]
                dest_subst = Template(notebook.dest).safe_substitute({
                    TARGET_LANG: lang_dir,
                    TARGET_EXTENSION: ext[1:] if ext.startswith('') else ext,
                    NOTEBOOK_TYPE: notebook_type_map.get(notebook_type, '')
                })
                if dest_subst.startswith(os.path.sep):
                    dest_subst = dest_subst[len(os.path.sep):]

                for f in matches:
                    target = path.normpath(joinpath(target_dir, dest_subst))
                    copy(f, target)
                    copied += 1

                if copied == 0:
                    error('Found no generated {0} {1} notebooks for "{2}"!'.
                        format(lang, notebook_type.value, notebook.src)
                    )

    verbose("Running master parse on {0}".format(src_path))
    master = notebook.master
    with TemporaryDirectory() as tempdir:
        try:
            params = master_parse.Params(
                path=src_path,
                output_dir=tempdir,
                databricks=True,
                ipython=False,
                scala=master.scala,
                python=master.python,
                r=master.r,
                sql=master.sql,
                instructor=True,
                exercises=True,
                answers=master.answers,
                notebook_heading_path=master.heading.path,
                add_heading=master.heading.enabled,
                notebook_footer_path=master.footer.path,
                add_footer=master.footer.enabled,
                encoding_in=master.encoding_in,
                encoding_out=master.encoding_out,
                enable_verbosity=verbosity_is_enabled(),
                copyright_year=build.course_info.copyright_year,
            )
            master_parse.process_notebooks(params)
            move_master_notebooks(master, tempdir)
        except Exception as e:
            error("Failed to process {0}\n    {1}: {2}".format(
                src_path, e.__class__.__name__, e.message
            ))
            raise

def copy_notebooks(build, labs_dir, dest_root):
    """
    Copy the notebooks to the destination directory.
    """
    os.makedirs(labs_dir)
    for notebook in build.notebooks:
        src_path = joinpath(build.source_base, notebook.src)
        if notebook.master_enabled():
            process_master_notebook(
                dest_root=dest_root,
                notebook=notebook,
                src_path=src_path,
                build=build
            )
        else:
            dest_path = joinpath(labs_dir, notebook.dest)
            copy(src_path, dest_path)

        remove_empty_subdirectories(dest_root)


def copy_instructor_notes(build, dest_root):
    # Starting at build.source_base, look for instructor notes and course
    # guides. Only keep the ones for the labs and slides we're using.
    if build.notebooks:
        notebook_dirs = set([path.dirname(n.src) for n in build.notebooks])
    else:
        notebook_dirs = set()

    if build.slides:
        slide_dirs = set([path.dirname(s.src) for s in build.slides])
    else:
        slide_dirs = set()

    def lives_under_one_of(dirs, to_match):
        for d in dirs:
            if d.startswith(to_match):
                return True
        return False

    notes_re = re.compile(r'^instructor[-_]notes[-._]', re.IGNORECASE)
    guide_re = re.compile(r'^guide\.', re.IGNORECASE)
    full_source_base = path.abspath(build.source_base)
    for (dirpath, _, filenames) in os.walk(build.source_base):
        for f in filenames:
            # Get the file path relative to the source file. With labs
            # (notebooks), if the file matches the instructor notes regex
            # AND anywhere under one of the notebook directories, copy it.
            #
            # For instructor guides, the guide must live in one of the
            # slides directories.
            rel_dir = path.abspath(dirpath)[len(full_source_base) + 1:]
            keep = False
            if notes_re.match(f) and lives_under_one_of(notebook_dirs, rel_dir):
                keep = True
            elif guide_re.match(f) and (rel_dir in slide_dirs):
                keep = True

            if keep:
                s = joinpath(dirpath, f)
                t = joinpath(dest_root,
                              build.instructor_dir,
                              INSTRUCTOR_NOTES_SUBDIR,
                              rel_dir,
                              f)
                verbose("Copying {0} to {1}".format(s, t))
                copy_info_file(s, t, build)
                continue


def make_dbc(gendbc, build, labs_dir, dbc_path):
    """
    Create a DBC file from the labs.
    """
    wd = path.dirname(labs_dir)
    with working_directory(wd):
        simple_labs_dir = path.basename(labs_dir)
        if verbosity_is_enabled():
            cmd = "{0} {1} {2} {3} {4} {5}".format(
                gendbc, "-v", "-f", build.top_dbc_folder_name, simple_labs_dir,
                dbc_path
            )
        else:
            cmd = "{0} {1} {2} {3} {4}".format(
                gendbc, "-f", build.top_dbc_folder_name, simple_labs_dir,
                dbc_path
            )

        verbose("\nIn {0}:\n{1}\n".format(wd, cmd))
        rc = os.system(cmd)
        if rc != 0:
            raise BuildError("Failed to create DBC: " + cmd)


def copy_slides(build, dest_root):
    """
    Copy the slides (if any).
    """
    if build.slides:
        for f in build.slides:
            src = joinpath(build.source_base, f.src)
            dest = joinpath(dest_root,
                             build.instructor_dir,
                             SLIDES_SUBDIR,
                             f.dest)
            copy(src, dest)


def copy_misc_files(build, dest_root):
    """
    Copy the miscellaneous files (if any).
    """
    if build.misc_files:
        for f in build.misc_files:
            s = joinpath(build.course_directory, f.src)
            t = joinpath(dest_root, f.dest)
            copy_info_file(s, t, build)


def copy_datasets(build, dest_root):
    """
    Copy the datasets (if any).
    """
    if build.datasets:
        for ds in build.datasets:
            for i in (ds.src, ds.license, ds.readme):
                source = joinpath(build.course_directory, i)
                target = joinpath(dest_root,
                                   build.student_dir,
                                   DATASETS_SUBDIR,
                                   ds.dest,
                                   path.basename(i))
                copy(source, target)


def remove_empty_subdirectories(directory):
    for dirpath, _, _ in os.walk(directory, topdown=False):
        if len(os.listdir(dirpath)) == 0:
            verbose("Deleting empty directory {0}".format(dirpath))
            os.rmdir(dirpath)


def write_version_notebook(dir, notebook_contents, version):
    nb_path = joinpath(dir, VERSION_NOTEBOOK_FILE.format(version))
    ensure_parent_dir_exists(nb_path)
    with codecs.open(nb_path, 'w', encoding='UTF-8') as out:
        out.write(notebook_contents)


def build_course(opts, build):

    if build.course_info.deprecated:
        die('{0} is deprecated and cannot be built.'.format(
            build.course_info.name
        ))

    gendbc = find_in_path('gendbc')

    dest_dir = (
        opts['--dest'] or
        joinpath(os.getenv("HOME"), "tmp", "curriculum", build.course_id)
    )

    verbose('Publishing to "{0}"'.format(dest_dir))
    if path.isdir(dest_dir):
        if not opts['--overwrite']:
            die(('Directory "{0}" already exists, and you did not ' +
                 'specify --overwrite.').format(dest_dir))

        rm_rf(dest_dir)

    for d in (build.instructor_dir, build.student_dir):
        mkdirp(joinpath(dest_dir, d))

    version = build.course_info.version
    version_notebook = Template(VERSION_NOTEBOOK_TEMPLATE).substitute({
        'course_name':     build.course_info.name,
        'version':         version,
        'build_timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
        'year':            build.course_info.copyright_year,
    })

    labs_full_path = joinpath(dest_dir, build.student_dir, STUDENT_LABS_SUBDIR)
    copy_notebooks(build, labs_full_path, dest_dir)
    copy_instructor_notes(build, dest_dir)
    write_version_notebook(labs_full_path, version_notebook, version)

    make_dbc(gendbc=gendbc,
             build=build,
             labs_dir=labs_full_path,
             dbc_path=joinpath(dest_dir, build.student_dir, STUDENT_LABS_DBC))

    instructor_labs = joinpath(dest_dir,
                                build.instructor_dir,
                                INSTRUCTOR_LABS_SUBDIR)
    if os.path.exists(instructor_labs):
        instructor_dbc = joinpath(dest_dir,
                                   build.instructor_dir,
                                   INSTRUCTOR_LABS_DBC)
        write_version_notebook(instructor_labs, version_notebook, version)
        make_dbc(gendbc, build, instructor_labs, instructor_dbc)
    copy_slides(build, dest_dir)
    copy_misc_files(build, dest_dir)
    copy_datasets(build, dest_dir)

    # Finally, remove the instructor labs folder and the student labs
    # folder.
    if not build.keep_lab_dirs:
        rm_rf(labs_full_path)
        rm_rf(instructor_labs)

    if errors > 0:
        raise BuildError("{0} error(s).".format(errors))

    print("\nPublished {0}, version {1} to {2}\n".format(
        build.course_info.name, build.course_info.version, dest_dir
    ))


def dbw(subcommand, args, capture_stdout=True):
    '''
    Invoke "databricks workspace" with specified arguments.

    :param subcommand: the "databricks workspace" subcommand
    :param args: arguments, as a list
    :param capture_stdout: True to capture and return standard output. False
                           otherwise.

    :return: A tuple of (returncode, parsed_json) on error,
             or (returncode, stdout) on success. If capture_stdout is False,
             then a successful result will return an empty string for stdout.
    '''
    dbw = find_in_path('databricks')
    try:
        full_args = [dbw, 'workspace', subcommand] + args
        verbose('+ {0}'.format(' '.join(full_args)))
        stdout_loc = subprocess.PIPE if capture_stdout else None
        p = subprocess.Popen(full_args,
                             stdout=stdout_loc, stderr=subprocess.STDOUT)
        if capture_stdout:
            stdout, stderr = p.communicate()
            stdout = stdout.decode('UTF-8')
        else:
            stdout = ''
            p.wait()

        if p.returncode is 0:
            return (p.returncode, stdout)
        elif stdout.startswith('Error: {'):
            j = json.loads(stdout.replace('Error: {', '{'))
            j['message'] = j.get('message', '').replace(r'\n', '\n')
            return (p.returncode, j)
        else:
            return (p.returncode, {'error_code': 'UNKNOWN', 'message': stdout})

    except OSError as e:
        return (1, {'error_code': 'OS_ERROR', 'message': e.message})


def ensure_shard_path_exists(shard_path):
    rc, res = dbw('ls', [shard_path])
    if rc == 0 and res.startswith(u'Usage:'):
        die('(BUG) Error in "databricks" command:\n{0}'.format(res))
    elif rc == 0:
        # Path exists.
        pass
    else:
        message = res.get('message', '?')
        if res.get('error_code', '?') == 'RESOURCE_DOES_NOT_EXIST':
            # All good
            die('Shard path "{0}" does not exist.'.format(message))
        else:
            # Some other error
            die('Unexpected error with "databricks": {0}'.format(message))


def ensure_shard_path_does_not_exist(shard_path):
    rc, res = dbw('ls', [shard_path])
    if rc == 0 and res.startswith('Usage:'):
        die('(BUG) Error in "databricks" command:\n{0}'.format(res))
    elif rc == 0:
        # Path exists.
        die('Shard path "{0}" already exists.'.format(shard_path))
    else:
        message = res.get('message', '?')
        if res.get('error_code', '?') == 'RESOURCE_DOES_NOT_EXIST':
            # All good
            pass
        else:
            # Some other error
            die('Unexpected error with "databricks": {0}'.format(message))


def expand_shard_path(shard_path):
    if shard_path.startswith('/'):
        return shard_path

    # Relative path. Look for DB_SHARD_HOME environment variable.
    home = os.getenv(DB_SHARD_HOME_VAR)
    if home is None:
        db_config = os.path.expanduser('~/.databrickscfg')
        if os.path.exists(db_config):
            cfg = SafeConfigParser()
            cfg.read(db_config)
            try:
                home = cfg.get('DEFAULT', 'home')
            except NoOptionError:
                pass

    if home is None:
        die(('Shard path "{0}" is relative, but environment variable {1} ' +
             'does not exist, and there is no "home" setting in {2}.').format(
            shard_path, DB_SHARD_HOME_VAR, db_config
        ))

    if shard_path == '':
        shard_path = home
    else:
        shard_path = '{0}/{1}'.format(home, shard_path)

    return shard_path



def notebook_is_transferrable(nb, build):
    nb_full_path = path.abspath(joinpath(build.source_base, nb.src))
    if not os.path.exists(nb_full_path):
        warning('Notebook "{0}" does not exist.'.format(nb_full_path))
        return False

    if not nb.upload_download:
        info('Skipping notebook "{0}": It has upload_download disabled.'.format(
            nb_full_path
        ))
        return False

    return True


def get_sources_and_targets(build):
    '''
    Get the list of source notebooks to be uploaded/downloaded and map them
    to their target names on the shard.

    :param build: the build

    :return: A dict of source names to partial-path target names
    '''
    template_data = {
        TARGET_LANG: '',
        NOTEBOOK_TYPE: '',
    }
    def map_notebook_dest(nb):
        template_data2 = {}
        template_data2.update(template_data)
        _, ext = path.splitext(nb.src)
        if ext:
            ext = ext[1:] # skip leading '.'

        template_data2[TARGET_EXTENSION] = ext
        return path.normpath(
            leading_slashes.sub(
                '', Template(nb.dest).safe_substitute(template_data2)
            )
        )

    res = {}
    notebooks = [nb for nb in build.notebooks
                 if notebook_is_transferrable(nb, build)]
    leading_slashes = re.compile(r'^/+')

    target_dirs = {}
    for nb in notebooks:
        dest = map_notebook_dest(nb)
        if nb.master.enabled:
            # The destination is a directory. Count how many notebooks
            # end up in each directory.
            target_dirs[dest] = target_dirs.get(dest, 0) + 1

    for nb in notebooks:
        nb_full_path = path.abspath(joinpath(build.source_base, nb.src))

        # Construct partial path from target path.
        base_with_ext = path.basename(nb_full_path)
        (base_no_ext, ext) = path.splitext(base_with_ext)
        if len(ext) > 0:
            ext = ext[1:] # remove the leading "."
        dest = map_notebook_dest(nb)

        res[nb_full_path] = dest

    return res


def upload_notebooks(build, shard_path):
    shard_path = expand_shard_path(shard_path)
    ensure_shard_path_does_not_exist(shard_path)

    notebooks = get_sources_and_targets(build)
    try:
        with TemporaryDirectory() as tempdir:
            info("Copying notebooks to temporary directory.")
            for nb_full_path, partial_path in notebooks.items():
                temp_path = joinpath(tempdir, partial_path)
                dir = path.dirname(temp_path)
                mkdirp(dir)
                verbose('Copying "{0}" to "{1}"'.format(nb_full_path, temp_path))
                copy(nb_full_path, temp_path)

            with working_directory(tempdir):
                info("Uploading notebooks to {0}".format(shard_path))
                rc, res = dbw('import_dir', ['.', shard_path], capture_stdout=False)
                if rc != 0:
                    raise UploadDownloadError(
                        "Upload failed: {0}".format(res.get('message', '?'))
                    )
                else:
                    info("Uploaded {0} notebooks to {1}.".format(
                        len(notebooks), shard_path
                    ))
    except UploadDownloadError as e:
        dbw('rm', [shard_path], capture_stdout=False)
        die(e.message)

def download_notebooks(build, shard_path):
    shard_path = expand_shard_path(shard_path)
    ensure_shard_path_exists(shard_path)

    # get_sources_and_targets() returns a dict of
    # local-path -> remote-partial-path. Reverse it. Bail if there are any
    # duplicate keys, because it's supposed to be 1:1.
    remote_to_local = {}
    for local, remote in get_sources_and_targets(build).items():
        if remote in remote_to_local:
            die('(BUG): Found multiple instances of remote path "{0}"'.format(
                remote
            ))
        remote_to_local[remote] = local

    with TemporaryDirectory() as tempdir:
        info("Downloading notebooks to temporary directory")
        with working_directory(tempdir):
            rc, res = dbw('export_dir', [shard_path, '.'])
            if rc != 0:
                die("Download failed: {0}".format(res.get('message', '?')))

            for remote, local in remote_to_local.items():
                if not path.exists(local):
                    warning(('Cannot find downloaded version of course ' +
                             'notebook "{0}".').format(local))
                print('"{0}" -> {1}'.format(remote, local))
                # Make sure there's a newline at the end of each file.
                move(remote, local, ensure_final_newline=True)

            # Are there any leftovers?
            leftover_files = []
            for root, dirs, files in os.walk('.'):
                for f in files:
                    leftover_files.append(path.relpath(joinpath(root, f)))
            if len(leftover_files) > 0:
                warning(("These files from {0} aren't in the build file and" +
                        "were not copied").format(shard_path))
                for f in leftover_files:
                    print("    {0}".format(f))

def list_notebooks(build):
    for notebook in build.notebooks:
        src_path = joinpath(build.source_base, notebook.src)
        print(src_path)

# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def main():

    opts = parse_args()

    if opts['--verbose']:
        set_verbosity(True, verbose_prefix='bdc: ')

    course_config = opts['BUILD_YAML'] or DEFAULT_BUILD_FILE

    try:
        build = load_build_yaml(course_config)

        if opts['--list-notebooks']:
            list_notebooks(build)
        elif opts['--upload']:
            upload_notebooks(build, opts['SHARD_FOLDER_PATH'])
        elif opts['--download']:
            download_notebooks(build, opts['SHARD_FOLDER_PATH'])
        else:
            build_course(opts, build)

    except ConfigError as e:
        die('Error in "{0}": {1}'.format(course_config, e.message))
    except BuildError as e:
        die(e.message)

if __name__ == '__main__':
    main()
