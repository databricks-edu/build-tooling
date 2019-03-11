#!/usr/bin/env python

from __future__ import annotations # PEP 563 (allows annotation forward refs)

import sys

import os
from os import path
import re
from datetime import datetime
from configparser import ConfigParser, NoOptionError
from enum import Enum
import master_parse
from gendbc import gendbc
from db_edu_util.notebooktools import parse_source_notebook, NotebookError
from db_edu_util import (db_cli, wrap2stdout, error, verbose, set_verbosity,
                         warn, verbosity_is_enabled, info, die,
                         EnhancedTextWrapper)
from db_edu_util.db_cli import DatabricksCliError
from grizzled.file import eglob
from bdc.bdcutil import *
from string import Template as StringTemplate
import dataclasses
from dataclasses import dataclass
from tempfile import TemporaryDirectory
import codecs
import shutil

from typing import (Sequence, Any, Type, TypeVar, Set, Optional, Dict,
                    AnyStr, Tuple, NoReturn, Generator, Union, Callable, Set)

__all__ = ['bdc_check_build', 'bdc_list_notebooks', 'bdc_build_course',
           'bdc_download', 'bdc_upload', 'bdc_check_build',
           'bdc_print_info']

# ---------------------------------------------------------------------------
# Constants
#
# (Some constants are below the class definitions.)
# ---------------------------------------------------------------------------

VERSION = "1.30.0-RC3"

DEFAULT_BUILD_FILE = 'build.yaml'
PROG = os.path.basename(sys.argv[0])

DB_SHARD_HOME_VAR = 'DB_SHARD_HOME'

USAGE = f"""
{PROG}, version {VERSION}

Usage:
  {PROG} (--version)
  {PROG} --info [--shell] [BUILD_YAML]
  {PROG} (-C | --check) [BUILD_YAML]
  {PROG} (-h | --help)
  {PROG} [-o | --overwrite] [-v | --verbose] [-d DEST | --dest DEST] [BUILD_YAML] 
  {PROG} --list-notebooks [BUILD_YAML]
  {PROG} --upload [-v | --verbose] [-P PROF | --dprofile PROF ] SHARD_PATH [BUILD_YAML]
  {PROG} --download [-v | --verbose] [-P PROF | --dprofile PROF ] SHARD_PATH [BUILD_YAML]

MASTER_CFG is the build tool's master configuration file.

BUILD_YAML is the build file for the course to be built. Defaults to {2}.

SHARD_PATH is the path to a folder on a Databricks shard, as supported
by the Databricks CLI. You must install databricks-cli and configure it
properly for --upload and --download to work.

Options:
  -h --help                Show this screen.
  -C --check               Parse the build file and validate that the referenced
                           paths actually exist.
  -d DEST --dest DEST      Specify output destination. Defaults to
                           ~/tmp/curriculum/<course_id>
  -o --overwrite           Overwrite the destination directory, if it exists.
  -v --verbose             Print what's going on to standard output.
  --info                   Display the course name and version, and exit
  --shell                  Used with --info, this option causes the course
                           name and version to be emitted as shell variables.
  --list-notebooks         List the full paths of all notebooks in a course
  --upload                 Upload all notebooks to a folder on Databricks.
  --download               Download all notebooks from a folder on Databricks,
                           copying them into their appropriate locations on the 
                           local file system, as defined in the build.yaml file.
  -P PROF --dprofile PROF  When uploading and downloading, pass authentication
                           profile PROF to the "databricks" commands. This
                           option corresponds exactly with the --profile
                           argument to "databricks".
  --version                Display version and exit.

"""

DEFAULT_INSTRUCTOR_FILES_SUBDIR = "InstructorFiles"
DEFAULT_INSTRUCTOR_LABS_DBC = "Instructor-Labs.dbc"
DEFAULT_STUDENT_FILES_SUBDIR = "StudentFiles"
DEFAULT_STUDENT_LABS_DBC = "Labs.dbc"       # in the student directory
SLIDES_SUBDIR = "Slides"                    # in the instructor directory
DATASETS_SUBDIR = "Datasets"                # in the student directory
INSTRUCTOR_NOTES_SUBDIR = "InstructorNotes" # in the instructor directory

# Post master-parse variables (and associated regexps)
TARGET_LANG = 'target_lang'
TARGET_EXTENSION = 'target_extension'
NOTEBOOK_TYPE = 'notebook_type'
OUTPUT_DIR = 'output_dir'
PROFILE_VAR = 'profile'

DEFAULT_PROFILES = {'amazon': 'Amazon', 'azure': 'Azure'}
PROFILE_ABBREVIATIONS = {'amazon' : 'am', 'azure': 'az'}

POST_MASTER_PARSE_VARIABLES = {
    TARGET_LANG:       variable_ref_patterns(TARGET_LANG),
    TARGET_EXTENSION:  variable_ref_patterns(TARGET_EXTENSION),
    NOTEBOOK_TYPE:     variable_ref_patterns(NOTEBOOK_TYPE),
    OUTPUT_DIR:        variable_ref_patterns(OUTPUT_DIR),
    PROFILE_VAR:       variable_ref_patterns(PROFILE_VAR),
}

# EXT_LANG is used when parsing the YAML file.
EXT_LANG = {'.py':    'Python',
            '.r':     'R',
            '.scala': 'Scala',
            '.sql':   'SQL'}

# LANG_EXT: Mapping of language (in lower case) to extension
LANG_EXT = dict([(v.lower(), k) for k, v in list(EXT_LANG.items())])

# Used to create a Scala version notebook in the top-level. This is a string
# template, with the following variables:
#
# {course_name}     - the course name
# {version}         - the version
# {build_timestamp} - the build timestamp, in printable format
VERSION_NOTEBOOK_TEMPLATE = """// Databricks notebook source

// MAGIC %md # Course: ${course_name}
// MAGIC * Version ${version}
// MAGIC * Built ${build_timestamp}
// MAGIC
// MAGIC Copyright \\u00a9 ${year} Databricks, Inc.
"""

# The version notebook file name. Use as a format string, with {0} as the
# version number.
VERSION_NOTEBOOK_FILE = "Version-{0}.scala"

ANSWERS_NOTEBOOK_PATTERN = re.compile('^.*_answers\..*$')

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

errors: int = 0

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------


class BuildError(Exception):
    pass


class UploadDownloadError(Exception):
    pass


class BuildConfigError(BuildError):
    pass


class UnknownFieldsError(BuildConfigError):
    def __init__(self,
                 parent_section: str,
                 section: str,
                 bad_keys: Set[str]):
        keys = ', '.join(bad_keys)
        super(BuildConfigError, self).__init__(
            f'"{parent_section}": Bad fields in "{section}" section: {keys}'
        )


# See https://github.com/python/typing/issues/58#issuecomment-326240794
NotebookTypeClass = TypeVar('NotebookTypeClass', bound='NotebookType')


class NotebookType(Enum):
    EXERCISES = 'exercises'
    INSTRUCTOR = 'instructor'
    ANSWERS = 'answers'

    @classmethod
    def default_mappings(cls: Type[NotebookTypeClass]) -> Dict[NotebookType, str]:
        return {
            NotebookType.EXERCISES:  'exercises',
            NotebookType.INSTRUCTOR: 'instructor',
            NotebookType.ANSWERS:    'answers',
        }

    def suffix_for(self) -> str:
        """
        Get the filename suffix for the notebook type (e.g., '_exercises').

        :return: the suffix
        """
        return NotebookType.suffixes()[self]

    @classmethod
    def suffixes(cls: Type[NotebookTypeClass]) -> Dict[NotebookType, str]:
        """
        Get a dict of NotebookType -> suffix mappings

        :return: the mappings
        """
        return {
            NotebookType.EXERCISES:  '_exercises',
            NotebookType.INSTRUCTOR: '_instructor',
            NotebookType.ANSWERS:    '_answers',
        }

    def __repr__(self):
        return f'NotebookType.{self.name}'


@dataclass(frozen=True)
class MiscFileData:
    """
    Stores miscellaneous file data.

    Fields:

    src:             path to source file
    dest:            path to destination
    is_template:     whether or not the source file is a template
    dest_is_dir:     whether the destination is a directory or a file
    only_in_profile: if set, the file is only defined for a particular profile
    """
    src: str
    dest: str
    is_template: bool
    dest_is_dir: bool
    only_in_profile: Optional[str]


@dataclass(frozen=True)
class SlideData:
    """
    Stores slide file data.

    Fields:

    src:  path to source file
    dest: path to destination
    """
    src: str
    dest: str


@dataclass(frozen=True)
class DatasetData:
    """
    Stores a dataset specification.

    Fields:

    src:     path to source file
    dest:    path to destination
    license: path to license file
    readme:  path to README
    """
    src: str
    dest: str
    license: str
    readme: str


@dataclass(frozen=True)
class MarkdownInfo:
    """
    Stores information on how to process Markdown source files.

    Fields:

    html_stylesheet: optional path to stylesheet
    """
    html_stylesheet: Optional[str]


@dataclass(frozen=True)
class NotebookHeading:
    """
    Stores notebook heading information.

    Fields:

    path:    path to heading file
    enabled: True if the heading is enabled, False if disabled
    """
    path: Optional[str]
    enabled: bool


@dataclass(frozen=True)
class NotebookFooter:
    """
    Stores notebook footer information.

    Fields:

    path:    path to footer file
    enabled: True if the footer is enabled, False if disabled
    """
    path: Optional[str]
    enabled: bool


@dataclass(frozen=True)
class BundleFile:
    """
    Information about a file to include in the bundle.

    Fields:

    src:    path to the source file
    dest:   path within the bundle
    """
    src:  str
    dest: str


@dataclass(frozen=True)
class Bundle:
    """
    Parsed bundle information.

    - zipfile: the zip file for the bundle
    - files: a list of BundleFile objects
    """
    zipfile: str
    files: Sequence[BundleFile] = dataclasses.field(default_factory=list)


@dataclass(frozen=True)
class OutputInfo:
    student_dir: str
    student_dbc: str
    instructor_dir: str
    instructor_dbc: str

    @property
    def student_labs_subdir(self) -> str:
        (base, _) = path.splitext(self.student_dbc)
        return joinpath(self.student_dir, base)

    @property
    def instructor_labs_subdir(self) -> str:
        (base, _) = path.splitext(self.instructor_dbc)
        return joinpath(self.instructor_dir, base)


@dataclass(frozen=True)
class CourseInfo(DefaultStrMixin):
    name: str
    version: str
    class_setup: str
    schedule: str
    instructor_prep: str
    copyright_year: str
    deprecated: bool
    course_type: master_parse.CourseType
    title: Optional[str] = None

    @property
    def course_id(self) -> str:
        """
        The course ID, which is a combination of the course name and the
        version.

        :return: the course ID string
        """
        return f'{self.name}-{self.version}'


@dataclass(frozen=True)
class NotebookDefaults(DefaultStrMixin):
    dest: Optional[str] = None
    master: Optional[Dict[str, Any]] = dataclasses.field(default_factory=dict)
    variables: Optional[Dict[str, str]] = dataclasses.field(default_factory=dict)


# See https://github.com/python/typing/issues/58#issuecomment-326240794
MasterParseInfoClass = TypeVar('MasterParseInfoClass', bound='MasterParseInfo')


class MasterParseInfo(DefaultStrMixin):
    """
    Parsed master parser data for a notebook.
    """
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
        'encoding_out': str,
        'debug': bool,
        'enable_templates': bool,
        'instructor_notes': str,
    }

    VALID_HEADING_FIELDS = {
        'path': str,
        'enabled': bool
    }

    VALID_FOOTER_FIELDS = {
        'path': str,
        'enabled': bool
    }

    def __init__(self,
                 enabled: bool = False,
                 python: bool = True,
                 scala: bool = True,
                 r: bool = False,
                 sql: bool = False,
                 answers: bool = True,
                 exercises: bool = True,
                 instructor: bool = True,
                 instructor_notes: Optional[str] = None,
                 heading: Optional[NotebookHeading] = None,
                 footer: Optional[NotebookFooter] = None,
                 encoding_in: str = 'UTF-8',
                 encoding_out: str = 'UTF-8',
                 enable_templates: bool = False,
                 debug: bool = False):
        """
        Create a new parsed master parse data object

        :param enabled:          whether master parsing is enabled
        :param python:           whether Python notebook generation is enabled
        :param scala:            whether Scala notebook generation is enabled
        :param r:                whether R notebook generation is enabled
        :param sql:              whether SQL notebook generation is enabled
        :param answers:          whether to generate answer notebooks
        :param exercises:        whether to generate exercises notebook
        :param instructor:       whether to generate instructor notebooks
        :param heading:          heading information (a NotebookHeading object)
        :param footer:           footer information (a NotebookFooter object)
        :param encoding_in:      the encoding of the source notebooks
        :param encoding_out:     the encoding to use when writing notebooks
        :param enable_templates: whether to treat Markdown cells as Mustache
                                 templates
        :param debug:            enable/disable debug messages for the master
                                 parse phase
        """
        if heading is None:
            heading = NotebookHeading(path=None, enabled=True)
        if footer is None:
            footer = NotebookFooter(path=None, enabled=True)
        self.enabled = enabled
        self.python = python
        self.scala = scala
        self.r = r
        self.sql = sql
        self.answers = answers
        self.exercises = exercises
        self.instructor = instructor
        self.instructor_notes = instructor_notes
        self.heading = heading
        self.footer = footer
        self.encoding_in = encoding_in
        self.encoding_out = encoding_out
        self.enable_templates = enable_templates
        self.debug = debug

    def lang_is_enabled(self, lang: str) -> bool:
        """
        Determine if a specific language is enabled.

        :param lang:  the name (string) for the language, in lower case

        :return: True if it's enable, False if not
        """
        return self.__getattribute__(lang)

    def enabled_langs(self) -> Sequence[str]:
        """
        Return a list of the enabled languages. e.g., ['scala', 'python']

        :return: the list of enabled languages, which could be empty
        """
        return [i for i in self.LANGUAGES if self.__getattribute__(i)]

    def update_from_dict(self, d: Dict[str, Any]) -> NoReturn:
        """
        Update the fields in this master parse record from a dictionary.
        The dictionary should represent a master parse dictionary (e.g., as
        parsed from YAML). Keys can be missing. Extra keys are ignored.

        :param d: the dictionary
        """
        for k in list(self.VALID_FIELDS.keys()):
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
    def extra_keys(cls: Type[MasterParseInfoClass],
                   d:   Dict[str, Any]) -> Optional[Set[str]]:
        """
        Check a dictionary of master parse values for extra (unknown) keys.

        :param d: the dictionary to check

        :return: any unknown keys, or None if there aren't any.
        """
        extra = set(d.keys()) - set(cls.VALID_FIELDS.keys())
        heading = d.get('heading') or {}
        for k in (set(heading.keys()) - set(cls.VALID_HEADING_FIELDS.keys())):
            extra.add(f'heading.{k}')

        if len(extra) == 0:
            extra = None

        return extra

    @classmethod
    def from_dict(cls: Type[MasterParseInfoClass],
                  d: Dict[str, Any]) -> MasterParseInfo:
        """
        Create a MasterParseData object from a dictionary of values.

        :param d: the dictionary.

        :return: The object. Throws exceptions on error. Extra keys are not
                 interpreted as an error here; callers can report those errors
                 with more context.
        """
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
            encoding_out=d.get('encoding_out', 'UTF-8'),
            debug=bool_field(d, 'debug', False)
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this object into a dictionary.

        :return: the dictionary of fields
        """
        res = {}
        res.update(self.__dict__)
        return res

    @classmethod
    def _parse_footer(cls: Type[MasterParseInfoClass],
                      footer_data: Dict[AnyStr, AnyStr]) -> NotebookFooter:
        if footer_data:
            footer = NotebookFooter(
                path=footer_data.get('path', DEFAULT_NOTEBOOK_FOOTER.path),
                enabled=bool_field(footer_data, 'enabled',
                                   DEFAULT_NOTEBOOK_FOOTER.enabled)
            )
        else:
            footer = NotebookFooter(path=None, enabled=True)

        return footer

    @classmethod
    def _parse_heading(cls: Type[MasterParseInfoClass],
                       heading_data: Dict[AnyStr, Any]) -> NotebookHeading:
        if heading_data:
            heading = NotebookHeading(
                path=heading_data.get('path', DEFAULT_NOTEBOOK_HEADING.path),
                enabled=bool_field(heading_data, 'enabled',
                                   DEFAULT_NOTEBOOK_HEADING.enabled)
            )
        else:
            heading = NotebookHeading(path=None, enabled=True)

        return heading


class NotebookData(DefaultStrMixin):
    """
    Parsed notebook data.
    """
    def __init__(self: NotebookData,
                 src: str,
                 dest: str,
                 upload_download: bool = True,
                 master: Optional[MasterParseInfo] = None,
                 variables: Optional[Dict[AnyStr, AnyStr]] = None,
                 only_in_profile: Optional[AnyStr] = None):
        """
        Captures parsed notebook data.

        :param src:             Partial or full path to the notebook
        :param dest:            Destination for the notebook, which can
                                contain variables. This value can be set
                                to `None`, as long as a destination is
                                available in the notebook defaults.
        :param upload_download: Whether upload and download are enabled
                                for this notebook.
        :param master:          The master parse data.
        :param variables:       Any variables for the notebook.
        :param only_in_profile: Profile to which notebook is restricted, if
                                any.
        """
        super(NotebookData, self).__init__()
        self.src = src
        self.dest = dest
        self.master = master
        self.upload_download = upload_download
        self.variables = variables or {}
        self.only_in_profile = only_in_profile

    def master_enabled(self) -> bool:
        """
        Determine whether master notebook processing is enabled for this
        notebook.

        :return: true or false
        """
        return self.master.enabled

    def total_master_langs(self) -> int:
        """
        Get the number of output languages produced by the master parser
        for this notebook.

        :return: 0 if the master parser isn't enabled. Number of output
                 languages otherwise.
        """
        return len(self.master.enabled_langs()) if self.master.enabled else 0

    def master_multiple_langs(self) -> bool:
        """
        Determine whether the master parser is parsing to multiple languages
        or not.

        :return: True if master parsing is enabled and parsing to multiple
                 languages; False if master parsing is disabled or is enabled
                 but with only one output language.
        """
        return self.total_master_langs() > 0


class BuildData(DefaultStrMixin):
    """
    Parsed build data.
    """
    def __init__(self: BuildData,
                 build_file_path: str,
                 top_dbc_folder_name: str,
                 source_base: str,
                 output_info: OutputInfo,
                 course_info: CourseInfo,
                 notebooks: Sequence[NotebookData],
                 slides: Sequence[SlideData],
                 datasets: Sequence[DatasetData],
                 misc_files: Sequence[MiscFileData],
                 keep_lab_dirs: bool,
                 markdown_cfg: MarkdownInfo,
                 notebook_type_map: Dict[NotebookType, str],
                 profiles: Optional[Set[master_parse.Profile]] = None,
                 variables: Optional[Dict[AnyStr, AnyStr]] = None,
                 bundle_info: Optional[Bundle] = None):
        """
        Create a new BuildData object.

        :param build_file_path:       path to the build file, for reference
        :param top_dbc_folder_name:   top-level directory in DBC, or None
        :param source_base:           value of source base field
        :param output_info:           info about the output directories and DBCs
        :param course_info:           parsed CourseInfo object
        :param notebooks:             list of parsed Notebook objects
        :param slides:                parsed SlideInfo object
        :param datasets:              parsed DatasetData object
        :param misc_files:            parsed MiscFileData object
        :param keep_lab_dirs:         value of keep_lab_dirs setting
        :param notebook_heading:      parsed NotebookHeading object
        :param markdown_cfg:          parsed MarkdownInfo object
        :param notebook_type_map:     a dict mapping notebook types to strings.
                                      Keys are from the NotebookType enum.
        :param profiles:              set of profiles, if any
        :param variables:             a map of user-defined variables
        :param bundle_info            Bundle data, if any
        """
        super(BuildData, self).__init__()
        self.build_file_path = build_file_path
        self.course_directory = path.dirname(build_file_path)
        self.notebooks = notebooks
        self.course_info = course_info
        self.source_base = source_base
        self.output_info = output_info
        self.slides = slides
        self.datasets = datasets
        self.profiles = set() if profiles is None else profiles

        if markdown_cfg.html_stylesheet:
            if path.isabs(markdown_cfg.html_stylesheet):
                self.markdown = markdown_cfg
            else:
                # Stylesheet is relative to the build directory. Resolve it
                # here.
                p = joinpath(path.dirname(build_file_path),
                             markdown_cfg.html_stylesheet)
                self.markdown = dataclasses.replace(markdown_cfg,
                                                    html_stylesheet=p)
        else:
            self.markdown = markdown_cfg

        self.misc_files = misc_files
        self.keep_lab_dirs = keep_lab_dirs
        self.notebook_type_map = notebook_type_map
        self.variables = variables or {}
        self.bundle_info = bundle_info

        if top_dbc_folder_name is None:
            top_dbc_folder_name = '${course_name}'

        folder_vars = merge_dicts(variables, {
            'course_name':    course_info.name,
            'course_version': course_info.version,
            'course_id':      self.course_id,
        })

        self.top_dbc_folder_name = VariableSubstituter(
            top_dbc_folder_name
        ).substitute(
            folder_vars
        )

    @property
    def course_type(self) -> master_parse.CourseType:
        return self.course_info.course_type

    @property
    def name(self) -> str:
        return self.course_info.name

    @property
    def course_id(self) -> str:
        """
        The course ID, which is a combination of the course name and the
        version.

        :return: the course ID string
        """
        return self.course_info.course_id

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
    'debug':            False
}

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def load_build_yaml(yaml_file: str) -> BuildData:
    """
    Load the YAML configuration file that defines the build for a particular
    class. Returns a BuildData object. Throws BuildConfigError on error.

    :param yaml_file   the path to the build file to be parsed
    :param output_dir  the top-level build output directory

    :return the Build object, representing the parsed build.yaml
    """
    def required(d: Dict[str, Any],
                 key: str,
                 where: str,
                 error: Optional[str] = None) -> Any:
        """
        Get a required key

        :param d:      the dictionary
        :param key:    the key
        :param where:  where in the file the key should be (for errors)
        :param error:  error message, or None for default
        :return: the value
        """
        v = d.get(key)
        if v is None:
            if error:
                msg = error
            else:
                msg = f'Missing required "{key}" in "{where}".'

            raise BuildConfigError(msg)

        return v

    def do_parse_level_substitutions(dest: str,
                                     src: str,
                                     allow_lang: bool = True,
                                     extra_vars: Dict[str, Any] = None) -> str:
        # Handles parse-time variable substitution. Some variables are
        # substituted later.
        if extra_vars is None:
            extra_vars = {}
        base_with_ext = path.basename(src)
        (base_no_ext, ext) = path.splitext(base_with_ext)

        if '@' in dest:
            raise BuildConfigError(
                'The "@" character is disallowed in destinations.'
            )

        # A certain set of variables is expanded only after master parsing; all
        # others are expanded here. Any references to post master-parse variables
        # (expanded in process_master_notebook) must be explicitly preserved
        # here. This logic escapes them by removing the "$" and surrounding the
        # rest with @ ... @. The escaping is undone, below.

        adj_dest = dest
        subbed = True
        while subbed:
            subbed = False
            for pats in list(POST_MASTER_PARSE_VARIABLES.values()):
                m = matches_variable_ref(pats, adj_dest)
                while m:
                    varname = m[1].replace(r'$', '')
                    var = f'@{varname}@'
                    adj_dest = m[0] + var + m[2]
                    subbed = True
                    m = matches_variable_ref(pats, adj_dest)

        fields = {
            'basename':    base_no_ext,
            'extension':   ext[1:] if ext.startswith('') else ext,
            'filename':    base_with_ext,
        }
        if allow_lang:
            fields['lang'] = EXT_LANG.get(ext, "???")

        fields.update(extra_vars)

        adj_dest = VariableSubstituter(adj_dest).safe_substitute(fields)

        # Restore escaped variables.
        escaped = re.compile(r'^([^@]*)@([^@]+)@(.*)$')
        m = escaped.match(adj_dest)
        while m:
            adj_dest = m.group(1) + '$' + m.group(2) + m.group(3)
            m = escaped.match(adj_dest)

        return adj_dest

    def parse_dict(d: Dict[str, Any],
                   fields_spec: Dict[str, Any],
                   outer_section: str,
                   section: str) -> Dict[str, Any]:
        res = {}
        for field, type in list(fields_spec.items()):
            if field not in d:
                continue
            if type is bool:
                try:
                    res[field] = bool_value(d[field])
                except ValueError as e:
                    raise BuildConfigError(
                        f'{outer_section}: Bad value for "{field}" in ' +
                        f'section "{section}": {e}'
                    )
                continue
            # Anything else gets copied as is for now.
            res[field] = d[field]

        return res

    def parse_master_section(data: Dict[str, Any],
                             section_name: str,
                             build_yaml_dir: str) -> Dict[str, Any]:
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
            heading_path = heading.get('path')
            if heading_path == 'DEFAULT':
                heading['path'] = None
            elif heading_path is not None:
                # Resolve the path, relative to the build file.
                if not path.isabs(heading_path):
                    heading_path = path.abspath(joinpath(build_yaml_dir,
                                                         heading_path))
                if not path.exists(heading_path):
                    raise BuildConfigError(
                        f'Footer file "{heading_path}" does not exist.'
                    )
                heading['path'] = heading_path

            master['heading'] = heading

        footer = master.get('footer')
        if footer:
            footer = parse_dict(footer, MasterParseInfo.VALID_FOOTER_FIELDS,
                                section_name, 'master.footer')
            footer_path = footer.get('path')
            if footer_path == 'DEFAULT':
                footer['path'] = None
            elif footer_path is not None:
                # Resolve the path, relative to the build field.
                if not path.isabs(footer_path):
                    footer_path = path.abspath(joinpath(build_yaml_dir,
                                                        footer_path))
                if not path.exists(footer_path):
                    raise BuildConfigError(
                        f'Footer file "{footer_path}" does not exist.'
                    )
                footer['path'] = footer_path

            master['footer'] = footer

        return master

    def parse_notebook_defaults(contents: Dict[str, Any],
                                section_name: str,
                                build_yaml_dir: str) -> NotebookDefaults:
        cfg = contents.get(section_name)
        if not cfg:
            return NotebookDefaults(dest=None, master=None)

        master = parse_master_section(dict_get_and_del(cfg, 'master', {}),
                                      'notebook_defaults', build_yaml_dir)
        variables = dict_get_and_del(cfg, 'variables', {})

        res = NotebookDefaults(dest=dict_get_and_del(cfg, 'dest', None),
                               master=master, variables=variables)

        if len(list(cfg.keys())) > 0:
            raise UnknownFieldsError("build", section_name, set(cfg.keys()))

        return res

    def parse_notebook(obj: Dict[str, Any],
                       notebook_defaults: NotebookDefaults,
                       extra_vars: Dict[str, str],
                       profiles: Optional[Set[master_parse.Profile]],
                       build_yaml_dir: str) -> Optional[NotebookData]:
        bad_dest = re.compile('^\.\./*|^\./*')
        src = required(obj, 'src', 'notebooks section')
        section = f'Notebook "{src}"'

        dest = obj.get('dest', notebook_defaults.dest)
        if not dest:
            raise BuildConfigError(
                f'Notebook "{src}": Missing "dest" section, and no default ' +
                '"dest" in notebook defaults.'
            )
        variables = merge_dicts(notebook_defaults.variables,
                                obj.get('variables', {}))
        all_extra_vars = merge_dicts(extra_vars, variables)
        dest = do_parse_level_substitutions(dest, src,
                                            extra_vars=all_extra_vars)
        if bool_field(obj, 'skip'):
            verbose(f'Skipping notebook {src}')
            return None

        master = MasterParseInfo() # defaults
        master.update_from_dict(notebook_defaults.master)
        nb_master = parse_master_section(obj.get('master', {}), section,
                                         build_yaml_dir)
        master.update_from_dict(nb_master)

        _, dest_ext = os.path.splitext(dest)
        if master.enabled and bad_dest.match(dest):
            raise BuildConfigError(
                f'Notebook "{src}": Relative destinations ("{dest}") are ' +
                'disallowed.'
            )

        if master.enabled:
            total_langs = len(master.enabled_langs())
            if (total_langs > 1):
                pat = POST_MASTER_PARSE_VARIABLES[TARGET_LANG]
                if not matches_variable_ref(pat, dest):
                    raise BuildConfigError(
                        f'Notebook "{src}": When multiple master parser ' +
                        'languages are used, you must substitute ' +
                        f'${TARGET_LANG} in the destination.'
                    )
        else:
            _, src_ext = os.path.splitext(src)
            if (not dest_ext) or (dest_ext != src_ext):
                raise BuildConfigError(
                    f'Notebook "{src}": "master" is disabled, so "dest" ' +
                    'should have extension "{src_ext}".'
                )
            for pats in list(POST_MASTER_PARSE_VARIABLES.values()):
                m = matches_variable_ref(pats, dest)
                if m:
                    raise BuildConfigError(
                        f'Notebook "{src}": "{m[1]}" found in "dest", but ' +
                        '"master" is disabled.'
                )

        prof = obj.get('only_in_profile')
        if prof:
            if not profiles:
                raise BuildConfigError(
                    f'Notebook "{src}": Bad value of "{prof}" for ' +
                    'only_in_profile. No profiles are defined in the build.'
                )
            profile_names = [p.name for p in profiles]
            if prof not in profile_names:
                name_str = ', '.join(profile_names)
                raise BuildConfigError(
                    f'Notebook "{src}": Bad value of "{prof}" for ' +
                    f'only_in_profile. Must be one of: {name_str}'
                )

        if prof and (not master.enabled):
            raise BuildConfigError(
                f'Notebook "{src}": only_in_profile is set, but master is ' +
                'not enabled.'
            )

        nb = NotebookData(
            src=src,
            dest=dest,
            master=master,
            upload_download=bool_field(obj, 'upload_download', True),
            variables=variables,
            only_in_profile=prof
        )

        return nb

    def parse_slide(obj: Dict[str, Any],
                    extra_vars: Dict[str, Any]) -> Optional[SlideData]:
        src = required(obj, 'src', 'notebooks')
        dest = required(obj, 'dest', 'notebooks')
        if bool_field(obj, 'skip'):
            verbose(f'Skipping slide {src}')
            return None
        else:
            return SlideData(
                src=src,
                dest=do_parse_level_substitutions(dest, src, allow_lang=False,
                                      extra_vars=extra_vars)
            )

    def parse_bundle(obj: Dict[str, Any],
                     output_info: OutputInfo,
                     course_info: CourseInfo,
                     extra_vars: Dict[str, str]) -> Optional[Bundle]:
        if not obj:
            return None

        files = obj.get('files')
        if not files:
            return None

        zip_vars = {
            'course_name': course_info.name,
            'course_version': course_info.version
        }
        zipfile = obj.get('zipfile')
        if zipfile:
            # Use safe_substitute, which leaves all other variables alone.
            zipfile = StringTemplate(zipfile).safe_substitute(zip_vars)
        else:
            zipfile = course_info.course_id + '.zip'

        file_list = []
        src_vars = {}
        src_vars.update(extra_vars)
        src_vars.update({
            'student_dbc': output_info.student_dbc,
            'instructor_dbc': output_info.instructor_dbc
        })

        for d in files:
            src = d['src']
            dest = d['dest']
            if not (dest or src):
                raise BuildConfigError(
                    '"bundle" has a file with no "src" or "dest".'
                )
            if not src:
                raise BuildConfigError('"bundle" has a file with no "src".')
            if not dest:
                raise BuildConfigError('"bundle" has a file with no "dest".')

            src = StringTemplate(src).substitute(src_vars)
            dest = do_parse_level_substitutions(dest, src, allow_lang=False,
                                    extra_vars=extra_vars)
            file_list.append(BundleFile(src=src, dest=dest))

        return Bundle(zipfile=zipfile, files=file_list)

    def parse_misc_file(obj: Dict[str, Any],
                        extra_vars: Dict[str, str]) -> Optional[MiscFileData]:
        src = required(obj, 'src', 'misc_files')
        dest = required(obj, 'dest', 'misc_files')

        if bool_field(obj, 'skip'):
            verbose(f'Skipping file {src}')
            return None
        else:
            dest = do_parse_level_substitutions(dest, src, allow_lang=False,
                                                extra_vars=extra_vars)

            mf = MiscFileData(
                src=src,
                dest=dest,
                dest_is_dir=obj.get('dest_is_dir', None),
                is_template=obj.get('template', False),
                only_in_profile=obj.get('only_in_profile', None)
            )
            # Sanity checks: A Markdown file can be translated to Markdown,
            # PDF or HTML. An HTML file can be translated to HTML or PDF.
            # is_template is disallowed for non-text files.
            if mf.is_template and (not is_text_file(src)):
                raise BuildConfigError(
                    f'Section misc_files: "{src}" is marked as a template' +
                    'but it is not a text file.'
                )

            # We can't check to see whether the target is a directory, since
            # nothing exists yet. But if it has an extension, we can assume it
            # is not a directory.
            if has_extension(dest):
                # It's a file, not a directory.
                if mf.dest_is_dir:
                    raise BuildConfigError(
                        f'Section misc_files: "{src}" uses a "dest" of ' +
                        f'"{dest}", which has an extension, so it is assumed ' +
                        'to be a file. But, "dest_is_dir" is set to true.'
                    )
                if is_markdown(src):
                    if not (is_pdf(dest) or is_html(dest) or is_markdown(dest)):
                        raise BuildConfigError(
                            f'Section misc_files: "{src}" is Markdown, the ' +
                            f'target ("{dest}") is not a directory and is ' +
                            'not PDF, HTML or Markdown.'
                        )
                if is_html(src):
                    if not (is_pdf(dest) or is_html(dest)):
                        raise BuildConfigError(
                            f'Section misc_files: "{src}" is HTML, the ' +
                            f'target ("{dest}") is not a directory and is ' +
                            'not PDF or HTML.'
                        )
            else:
                # No extension. Assume dest_is_dir is True, if not set.
                if mf.dest_is_dir is None:
                    mf = dataclasses.replace(mf, dest_is_dir=True)

                # Some simple sanity checks.
                if (not mf.dest_is_dir) and (dest in ('.', '..')):
                    raise BuildConfigError(
                        f'Section misc_files: "{src}" has a "dest" of ' +
                        f'"{dest}", but "dest_is_dir" is set to false. ' +
                        "That's just silly."
                    )

            return mf


    def parse_dataset(obj: Dict[str, Any],
                      extra_vars: Dict[str, Any],
                      build_yaml_dir: str) -> Optional[DatasetData]:
        src = required(obj, 'src', 'notebooks')
        dest = required(obj, 'dest', 'notebooks')
        if bool_field(obj, 'skip'):
            verbose(f'Skipping data set {src}')
            return None
        else:
            src_dir = path.dirname(src)
            license = joinpath(src_dir, 'LICENSE.md')
            readme = joinpath(src_dir, 'README.md')
            p = joinpath(build_yaml_dir, src)
            if not path.exists(p):
                raise BuildConfigError(f'Dataset file "{p}" does not exist')

            for i in (license, readme):
                p = joinpath(build_yaml_dir, i)
                if not path.exists(p):
                    raise BuildConfigError(
                        f'Dataset "{src}": Required "{p}" does not exist.'
                    )
                if os.stat(p).st_size == 0:
                    raise BuildConfigError(f'Dataset "{src}": "{p}" is empty.')

            adj_dest = do_parse_level_substitutions(
                dest, src, allow_lang=False, extra_vars=extra_vars
            )
            return DatasetData(src=src, dest=adj_dest, license=license,
                               readme=readme)

    def parse_file_section(section: Dict[str, Any],
                           parse: Callable[[Any, *Any], Any],
                           *args: Any) -> Tuple:
        # Use the supplied parse function to parse each element in the
        # supplied section, filtering out None results from the function.
        # Convert the entire result to a tuple.
        return tuple(
            [o for o in [parse(i, *args) for i in section] if o != None]
        )

    def parse_markdown(obj: Dict[str, Any]) -> MarkdownInfo:
        if obj:
            stylesheet = obj.get('html_stylesheet')
        else:
            stylesheet = None
        return MarkdownInfo(html_stylesheet=stylesheet)

    def parse_notebook_types(contents: Dict[str, Any]) -> Dict[NotebookType, Any]:
        res = NotebookType.default_mappings()
        names_to_keys = dict([(t.value, t) for t in NotebookType])

        invalid_keys = set()
        for k, v in list(contents.get('notebook_type_name', {}).items()):
            t = names_to_keys.get(k)
            if not t:
                invalid_keys.add(k)
            else:
                res[t] = v

        if invalid_keys:
            key_str = ', '.join(invalid_keys)
            raise BuildConfigError(
                f'Unknown key(s) in "notebook_type_name" section: {key_str}'
            )
        return res

    def parse_min_version(key: str, value: str) -> Optional[Tuple[int, int]]:
        res = contents.get(key)
        if res is not None:
            if isinstance(res, float):
                raise BuildConfigError(
                    f'"{key}" of the form <major>.<minor> must be quoted.'
                )

            try:
                # Ignore the match version.
                res = parse_version_string(res)[0:2]
            except ValueError as e:
                raise BuildConfigError(f'Bad value of "{res}" for "{key}": {e}')

        return res

    def parse_course_type(data: Dict[str, Any],
                          section: str) -> master_parse.CourseType:
        course_type = data.get('type')
        if not course_type:
            raise BuildConfigError(
                f'Missing required "{section}.type" setting in "{yaml_file}"'
            )

        if course_type.lower() == 'self-paced':
            return master_parse.CourseType.SELF_PACED
        if course_type.lower() == 'ilt':
            return master_parse.CourseType.ILT

        raise BuildConfigError(
            f'Unknown value of "{course_type}" for "{course_type}.type". ' +
            'Legal values are "ilt" and "self-paced".'
        )

    def parse_course_info(course_info_cfg: Dict[str, Any],
                          section_name: str) -> CourseInfo:
        ilt_only = {
            'class_setup':     None,
            'schedule':        None,
            'instructor_prep': None
        }

        name = required(course_info_cfg, 'name', section_name)
        version = required(course_info_cfg, 'version', section_name)
        ilt_only['class_setup'] = course_info_cfg.get('class_setup')
        ilt_only['schedule'] = course_info_cfg.get('schedule')
        ilt_only['instructor_prep'] = course_info_cfg.get('prep')
        course_type = parse_course_type(course_info_cfg, section_name)
        deprecated = course_info_cfg.get('deprecated', False)
        copyright_year = course_info_cfg.get('copyright_year',
                                             str(datetime.now().year))

        if type == master_parse.CourseType.SELF_PACED:
            for k, v in list(ilt_only.items()):
                if v:
                    warn(f'course_info.{k} is ignored for self-paced courses')

                ilt_only[k] = None

        return CourseInfo(
            name=name,
            title=course_info_cfg.get('title', name),
            version=version,
            class_setup=ilt_only['class_setup'],
            schedule=ilt_only['schedule'],
            instructor_prep=ilt_only['instructor_prep'],
            course_type=course_type,
            deprecated=deprecated,
            copyright_year=copyright_year
        )

    def parse_output_info(contents: Dict[str, Any]) -> OutputInfo:
        student_dir = contents.get('student_dir', DEFAULT_STUDENT_FILES_SUBDIR)
        instructor_dir = contents.get('instructor_dir',
                                      DEFAULT_INSTRUCTOR_FILES_SUBDIR)
        student_dbc = contents.get('student_dbc', DEFAULT_STUDENT_LABS_DBC)
        instructor_dbc = contents.get('instructor_dbc',
                                      DEFAULT_INSTRUCTOR_LABS_DBC)

        for (k, v) in (('student_dbc', student_dbc),
                       ('instructor_dbc', instructor_dbc)):
            if path.dirname(v) != '':
                raise BuildConfigError(
                    f'"{k}" value "{v}" is not a simple file name.'
                )

        if student_dir == instructor_dir:
            raise BuildConfigError(
                '"student_dir" and "instructor_dir" cannot be the same. ' +
                f'"student_dir" is "{student_dir}". ' +
                f'"instructor_dir" is "{instructor_dir}".'
            )

        return OutputInfo(student_dir=student_dir,
                          instructor_dir=instructor_dir,
                          student_dbc=student_dbc,
                          instructor_dbc=instructor_dbc)


    def parse_profiles(contents: Dict[str, Any]) -> Set[master_parse.Profile]:
        profiles = contents.get('profiles')
        use_profiles = bool_field(contents, 'use_profiles', False)
        if profiles and use_profiles:
            raise BuildConfigError(
                'You cannot specify both "use_profiles" and "profiles".'
            )

        if profiles:
            res = set()
            for thing in profiles:
                if isinstance(thing, dict):
                    if len(list(thing.keys())) != 1:
                        raise BuildConfigError(f'Malformed profile: {thing}')

                    n = list(thing.keys())[0]
                    v = thing[n]
                    if not isinstance(v, str):
                        raise BuildConfigError(
                            f'The value of profile "{n}" ("{v}") is not ' +
                            'a string.'
                        )

                    res.add(master_parse.Profile(name=n, value=v))
                    continue

                if isinstance(thing, str):
                    res.add(master_parse.Profile(name=thing, value=thing))
                    continue

                raise BuildConfigError(
                    f'Profile "{thing}" is neither a simple string nor a ' +
                    '"name: value"'
                )
        else:
            warn('"use_profiles" is deprecated. Use explicit profiles.')
            res = {master_parse.Profile(name='amazon', value='Amazon'),
                   master_parse.Profile(name='azure', value='azure')}

        return res

    # Main function logic

    verbose(f"Loading {yaml_file}...")
    contents = read_yaml_file(yaml_file)

    bdc_min_version = parse_min_version(
       'bdc_min_version', required(contents, 'bdc_min_version', 'build')
    )

    cur_major_minor = parse_version_string(VERSION)[0:2]
    if bdc_min_version > cur_major_minor:
        version_str = '.'.join(map(str, bdc_min_version))
        raise BuildConfigError(
            f"This build requires bdc version {version_str}.x or greater, " +
            f"but you're using bdc version {VERSION}."
        )

    profiles = parse_profiles(contents)
    variables = contents.get('variables', {})
    notebooks_cfg = required(contents, 'notebooks', 'build')
    slides_cfg = contents.get('slides', [])
    misc_files_cfg = contents.get('misc_files', [])
    datasets_cfg = contents.get('datasets', [])
    course_info_cfg = required(contents, 'course_info', 'build')
    course_info = parse_course_info(course_info_cfg, 'course_info')

    src_base = required(contents, 'src_base', 'build')
    build_yaml_full = path.abspath(yaml_file)
    build_yaml_dir = path.dirname(build_yaml_full)
    src_base = path.abspath(joinpath(build_yaml_dir, src_base))

    notebook_defaults = parse_notebook_defaults(contents, 'notebook_defaults',
                                                build_yaml_dir)

    if slides_cfg:
        slides = parse_file_section(slides_cfg, parse_slide, variables)
    else:
        slides = None

    if datasets_cfg:
        datasets = parse_file_section(datasets_cfg, parse_dataset, variables,
                                      build_yaml_dir)
    else:
        datasets = None

    if misc_files_cfg:
        misc_files = parse_file_section(misc_files_cfg, parse_misc_file,
                                        variables)
    else:
        misc_files = None

    if notebooks_cfg:
        notebooks = parse_file_section(notebooks_cfg, parse_notebook,
                                       notebook_defaults, variables,
                                       profiles, build_yaml_dir)

        # If there are any profiles in the notebooks, but no profiles in the
        # build, abort.
        nb_profiles = {n.only_in_profile for n in notebooks if n.only_in_profile}
        if (len(profiles) == 0) and (len(nb_profiles) > 0):
            raise BuildConfigError(
                'At least one notebook has "only_in_profile" set, but the ' +
                'build does not specify any profiles.'
            )

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
            version_str = '.'.join(map(str, required_master_min_version))
            raise BuildConfigError(
                f"This build requires master_parse version {version_str}.x " +
                "or greater, but you're using master_parse version " +
                f"{master_parse.VERSION}."
            )

    output_info = parse_output_info(contents)
    bundle_info = parse_bundle(contents.get('bundle'), output_info,
                               course_info, variables)

    data = BuildData(
        build_file_path=build_yaml_full,
        top_dbc_folder_name=contents.get('top_dbc_folder_name'),
        course_info=course_info,
        output_info=output_info,
        notebooks=notebooks,
        slides=slides,
        datasets=datasets,
        source_base=src_base,
        misc_files=misc_files,
        keep_lab_dirs=bool_field(contents, 'keep_lab_dirs'),
        markdown_cfg=parse_markdown(contents.get('markdown')),
        notebook_type_map=parse_notebook_types(contents),
        variables=variables,
        profiles=profiles,
        bundle_info=bundle_info
    )

    return data


def parse_args() -> Dict[str, Any]:
    """
    Parse the command line parameters.
    """
    from docopt import docopt
    return docopt(USAGE, version=VERSION)


def expand_template(src_template_file: str,
                    build: BuildData,
                    tempdir: str,
                    profile: Optional[master_parse.Profile]):
    import pystache

    variables = {}
    if build.variables:
        variables['variables'] = build.variables

    if profile:
        for p in build.profiles:
            if profile == p:
                variables[p.name] = p.value
            else:
                variables[p.name] = ''

    course_info_vars = {}
    for k, v in list(build.course_info.__dict__.items()):
        if v is None:
            continue
        if isinstance(v, Enum):
            v = v.value
        course_info_vars[k] = str(v)
    variables['course_info'] = course_info_vars

    output = joinpath(tempdir, path.basename(src_template_file))
    with codecs.open(src_template_file, mode='r', encoding='utf8') as i:
        with codecs.open(output, mode='w', encoding='utf8') as o:
            o.write(pystache.render(i.read(), variables))

    return output

# For copy_info_files and related logic:
#
# This is a table of special source file type to target file type
# processors. If the source type has a key in this table, then it
# is processed specially, and there MUST be an entry for the target type,
# or an error occurs. If the source type has no key in this table, then
# it is just copied as is. See _get_type().
INFO_PROCESSORS = {
    # Table that maps a source type and a target type to a consistent
    # three-arg lambda (src, dest, build) for generating the target.

    # src_type -> target_type -> lambda
    # The type is also the extension
    'md':
        {
            'html':
                lambda src, dest, build: markdown_to_html(
                    src, dest, stylesheet=build.markdown.html_stylesheet
                ),
            'pdf':
                 lambda src, dest, build: markdown_to_pdf(
                     src, dest, stylesheet=build.markdown.html_stylesheet
                 ),
             'md':
                 lambda src, dest, build: copy(src, dest)
         },
    'html':
        {
            'pdf':
                lambda src, dest, build: html_to_pdf(src, dest),
            'html':
                lambda src, dest, build: copy(src, dest)
        }
}

def _get_type(f: str) -> Optional[str]:
    if is_markdown(f):
        return 'md'
    if is_pdf(f):
        return 'pdf'
    if is_html(f):
        return 'html'
    return None

def _convert_and_copy_info_file(src: str,
                                dest: str,
                                build: BuildData) -> NoReturn:
    """
    Workhorse function: Takes the source and target, looks up how to process
    them, and processes them.

    :param src:    the source file
    :param dest:   the destination file (not directory)
    :param build:  the parsed build information

    """
    src_type = _get_type(src)
    dest_type = _get_type(dest)

    if src_type is None:
        # Not a special type that we have to convert. Just copy.
        copy(src, dest)
    elif dest_type is None:
        # Source type is a special type (Markdown, HTML), and the destination
        # (a) isn't marked as a directory, and (b) isn't a type we understand.
        # Treat it as a straight copy.
        shutil.copy(src, dest)
    else:
        proc = INFO_PROCESSORS.get(src_type, {}).get(dest_type, None)
        if proc is None:
            raise Exception(f'(BUG): No processor. "{src}" -> "{dest}".')

        proc(src, dest, build)


def copy_info_file(src_file: str,
                   target: str,
                   is_template: bool,
                   build: BuildData,
                   profile: Optional[master_parse.Profile]) -> NoReturn:
    """
    Copy a file that contains some kind of readable information (e.g., a
    Markdown file, a PDF, etc.). If the file is a Markdown file, it is also
    converted to HTML and copied.
    """
    with TemporaryDirectory() as tempdir:
        if is_template:
            real_src = expand_template(src_file, build, tempdir, profile)
        else:
            real_src = src_file

        # Okay to check for directory here. It should've been created already.
        if not path.isdir(target):
            # Copy and/or generate one file.
            _convert_and_copy_info_file(real_src, target, build)

        else:
            # Is a directory. What we generate depends on the input.
            # By this point, it has to exist.
            src_type = _get_type(src_file)
            if src_type is None:
                # Just a copy.
                base = path.basename(src_file)
                copy(real_src, joinpath(target, base))
            else:
                dest_map = INFO_PROCESSORS.get(src_type)
                if dest_map is None:
                    raise BuildError(
                        f'(BUG): Processor mismatch. "{src_file}" -> "{target}".'
                    )

                for dest_type in list(dest_map.keys()):
                    (base, _) = path.splitext(path.basename(src_file))
                    out = joinpath(target, base + '.' + dest_type)
                    _convert_and_copy_info_file(real_src, out, build)



def process_master_notebook(dest_root: str,
                            notebook: NotebookData,
                            src_path: str,
                            build: BuildData,
                            profile: Optional[master_parse.Profile]) -> NoReturn:
    """
    Process a master notebook.

    :param dest_root:   top-level target directory for build
    :param notebook:    the notebook data from the build YAML
    :param src_path:    the pre-calculated path to the source notebook
    :param dest_path:   the path to the target directory, calculated
                        from dest_root and notebook.dest
    :param build        parsed build data
    :param profile:     build profile, or None

    :return: None
    """
    verbose(f"notebook={notebook}\ndest_root={dest_root}")
    notebook_type_map = build.notebook_type_map
    student_labs_subdir = build.output_info.student_labs_subdir
    instructor_labs_subdir = build.output_info.instructor_labs_subdir
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
                fields = merge_dicts(notebook.variables, {
                    TARGET_LANG: lang_dir,
                    TARGET_EXTENSION: ext[1:] if ext.startswith('.') else ext,
                    NOTEBOOK_TYPE: notebook_type_map.get(notebook_type, '')
                })
                dest_subst = VariableSubstituter(
                    notebook.dest
                ).safe_substitute(
                    fields
                )
                if dest_subst.startswith(os.path.sep):
                    dest_subst = dest_subst[len(os.path.sep):]

                dest_base, _ = os.path.splitext(os.path.basename(dest_subst))
                fields['target_basename'] = dest_base


                for f in matches:
                    target = path.normpath(joinpath(target_dir, dest_subst))
                    copy(f, target)
                    copied += 1

                if copied == 0:
                    error(
                        f'Found no generated {lang} {notebook_type.value} ' +
                        f'notebooks for "{notebook.src}"!'
                    )

    def copy_instructor_notes(temp_file: str, final_dest: str) -> NoReturn:
        # Need to do some substitution here. We need to get a fully-substituted
        # destination, from which we can then extract the base file name.
        lang = list(EXT_LANG.values())[0] # Just choose one. It doesn't matter.
        ext = LANG_EXT[lang.lower()]
        nb_dest_subst = VariableSubstituter(notebook.dest).safe_substitute(
            merge_dicts(notebook.variables, {
                TARGET_LANG: lang,
                TARGET_EXTENSION: ext[1:] if ext.startswith('.') else ext,
                NOTEBOOK_TYPE: notebook_type_map.get(NotebookType.EXERCISES, '')
            })
        )

        target_basename, _ = os.path.splitext(os.path.basename(nb_dest_subst))

        # Now we can do substitution on the instructor notes target.
        final_dest = VariableSubstituter(final_dest).safe_substitute(
            merge_dicts(notebook.variables, {'target_basename': target_basename})
        )

        # Copy the generated Markdown file to the target destination.
        parent = os.path.dirname(final_dest)
        if not os.path.exists(parent):
            mkdirp(parent)
        verbose(f'+ cp {temp_file} {final_dest}')
        _convert_and_copy_info_file(temp_file, final_dest, build)

        # Convert to HTML.
        no_ext_path, _ = os.path.splitext(final_dest)
        html_path = f'{no_ext_path}.html'
        pdf_path = f'{no_ext_path}.pdf'
        markdown_to_html(final_dest, html_path,
                         stylesheet=build.markdown.html_stylesheet)
        html_to_pdf(html_path, pdf_path)

    verbose(f"Running master parse on {src_path}")
    master = notebook.master
    extra_template_vars = {}
    extra_template_vars.update(build.variables)
    extra_template_vars.update(notebook.variables)
    with TemporaryDirectory() as tempdir:
        try:
            if notebook.master.instructor_notes:
                temp_instructor_notes = os.path.join(tempdir, 'notes.md')
            else:
                temp_instructor_notes = None
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
                active_profile=profile,
                all_profiles=build.profiles,
                course_type=build.course_info.course_type,
                enable_debug=master.debug,
                enable_templates=master.enable_templates,
                instructor_notes_file=temp_instructor_notes,
                extra_template_vars=extra_template_vars
            )

            master_parse.process_notebooks(params)
            move_master_notebooks(master, tempdir)

            if temp_instructor_notes and os.path.exists(temp_instructor_notes):
                copy_instructor_notes(
                    temp_instructor_notes,
                    os.path.join(dest_root, notebook.master.instructor_notes)
                )

        except Exception as e:
            e_cls = e.__class__.__name__
            error(f"Failed to process {src_path}\n    {e_cls}: {e}")
            raise

def copy_notebooks(build: BuildData,
                   labs_dir: str,
                   dest_root: str,
                   profile: Optional[master_parse.Profile]) -> NoReturn:
    """
    Copy the notebooks to the destination directory.
    """
    os.makedirs(labs_dir)

    for notebook in build.notebooks:
        src_path = joinpath(build.source_base, notebook.src)
        if (profile and notebook.only_in_profile and
                notebook.only_in_profile != profile):
            info(
                f'Suppressing notebook "{src_path}", which is ' +
                f'{profile.name}-only.'
            )
            continue

        if notebook.master_enabled():
            process_master_notebook(
                dest_root=dest_root,
                notebook=notebook,
                src_path=src_path,
                build=build,
                profile=profile
            )
        else:
            dest_path = joinpath(labs_dir, notebook.dest)
            copy(src_path, dest_path)

        remove_empty_subdirectories(dest_root)


def copy_instructor_notes(build: BuildData,
                          dest_root: str,
                          profile: Optional[master_parse.Profile]) -> NoReturn:
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

    notes_re = re.compile(r'^instructor[-_]?notes[-._]', re.IGNORECASE)
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
                             build.output_info.instructor_dir,
                             INSTRUCTOR_NOTES_SUBDIR,
                             rel_dir,
                             f)
                (base, _) = path.splitext(path.basename(f))
                verbose(f"Copying {s} to {t}")
                copy_info_file(s, t, False, build, profile)
                if is_html(s):
                    html = s
                else:
                    html = None

                if is_markdown(s):
                    t = joinpath(dest_root,
                                 build.output_info.instructor_dir,
                                 INSTRUCTOR_NOTES_SUBDIR,
                                 rel_dir,
                                 f"{base}.html")
                    html = t
                    markdown_to_html(s, t,
                                     stylesheet=build.markdown.html_stylesheet)

                if html:
                    t = joinpath(dest_root,
                                 build.output_info.instructor_dir,
                                 INSTRUCTOR_NOTES_SUBDIR,
                                 rel_dir,
                                 f"{base}.pdf")
                    html_to_pdf(html, t)

                continue


def make_dbc(build: BuildData, labs_dir: str, dbc_path: str) -> NoReturn:
    """
    Create a DBC file from the labs.
    """
    try:
        gendbc(source_dir=labs_dir,
               encoding="utf-8",
               dbc_path=dbc_path,
               dbc_folder=build.top_dbc_folder_name,
               flatten=False,
               verbose=verbosity_is_enabled(),
               debugging=False)
    finally:
        pass


def copy_slides(build: BuildData, dest_root: str) -> NoReturn:
    """
    Copy the slides (if any).
    """
    if build.slides:
        for f in build.slides:
            src = joinpath(build.source_base, f.src)
            dest = joinpath(dest_root,
                             build.output_info.instructor_dir,
                             SLIDES_SUBDIR,
                             f.dest)
            copy(src, dest)


def copy_misc_files(build: BuildData,
                    dest_root: str,
                    profile: Optional[master_parse.Profile]) -> NoReturn:
    """
    Copy the miscellaneous files (if any).
    """
    if build.misc_files:
        for f in build.misc_files:
            if f.only_in_profile and (f.only_in_profile != profile):
                continue

            s = joinpath(build.course_directory, f.src)

            dest = f.dest
            if dest == '.':
                dest = dest_root

            t = joinpath(dest_root, dest)
            if f.dest_is_dir and (not path.isdir(t)):
                os.mkdir(t)
            copy_info_file(s, t, f.is_template, build, profile)


def copy_datasets(build: BuildData, dest_root: str) -> NoReturn:
    """
    Copy the datasets (if any).
    """
    if build.datasets:
        def target_for(file, dest):
            return joinpath(dest_root,
                            build.output_info.student_dir,
                            DATASETS_SUBDIR,
                            dest,
                            file)

        for ds in build.datasets:
            source = joinpath(build.course_directory, ds.src)
            copy(source, target_for(path.basename(source), ds.dest))

            css = build.markdown.html_stylesheet
            for i in (ds.license, ds.readme):
                source = joinpath(build.course_directory, i)
                (base, _) = path.splitext(path.basename(i))
                pdf = target_for(f"{base}.pdf", ds.dest)
                html = target_for(f"{base}.html", ds.dest)
                markdown_to_html(source, html, stylesheet=css)
                html_to_pdf(html, pdf)


def remove_empty_subdirectories(directory: str) -> NoReturn:
    for dirpath, _, _ in os.walk(directory, topdown=False):
        if len(os.listdir(dirpath)) == 0:
            verbose(f"Deleting empty directory {dirpath}")
            os.rmdir(dirpath)


def write_version_notebook(dir: str,
                           notebook_contents: str,
                           version: str) -> NoReturn:
    nb_path = joinpath(dir, VERSION_NOTEBOOK_FILE.format(version))
    ensure_parent_dir_exists(nb_path)
    with codecs.open(nb_path, 'w', encoding='UTF-8') as out:
        out.write(notebook_contents)


def bundle_course(build: BuildData,
                  dest_dir: str,
                  profile: Optional[master_parse.Profile]) -> NoReturn:
    from zipfile import ZipFile

    # Expand any run-time variables in zipfile and dest.
    if profile:
        vars = {PROFILE_VAR: profile.name}
    else:
        vars = {PROFILE_VAR: ''}

    t = StringTemplate(joinpath(dest_dir, build.bundle_info.zipfile))
    zip_path = t.safe_substitute(vars)
    print(f'Writing bundle {zip_path}')

    with ZipFile(zip_path, 'w') as z:
        for file in build.bundle_info.files:
            src = joinpath(dest_dir, file.src)
            if not (path.exists(src)):
                raise BuildError(
                    f'While building bundle, cannot find "{src}".'
                )
            if path.isdir(src):
                raise BuildError(
                    f'Cannot make bundle: Source "{src}" is a directory'
                )

            dest = StringTemplate(file.dest).safe_substitute(vars)
            z.write(src, dest)


def do_build(build: BuildData,
             base_dest_dir: str,
             profile: Optional[master_parse.Profile] = None) -> NoReturn:
    if profile:
        dest_dir = joinpath(base_dest_dir, profile.name)
    else:
        dest_dir = base_dest_dir

    for d in (build.output_info.instructor_dir, build.output_info.student_dir):
        mkdirp(joinpath(dest_dir, d))

    version = build.course_info.version
    fields = merge_dicts(build.variables, {
        'course_name':     build.course_info.name,
        'version':         version,
        'build_timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
        'year':            build.course_info.copyright_year,
    })
    version_notebook = VariableSubstituter(
        VERSION_NOTEBOOK_TEMPLATE
    ).substitute(
        fields
    )

    labs_full_path = joinpath(dest_dir, build.output_info.student_labs_subdir)
    copy_notebooks(build, labs_full_path, dest_dir, profile)
    copy_instructor_notes(build, dest_dir, profile)
    write_version_notebook(labs_full_path, version_notebook, version)

    student_dbc = joinpath(
        dest_dir, build.output_info.student_dir, build.output_info.student_dbc
    )
    make_dbc(build=build,
             labs_dir=labs_full_path,
             dbc_path=student_dbc)

    instructor_labs = joinpath(
        dest_dir, build.output_info.instructor_labs_subdir
    )
    if os.path.exists(instructor_labs):
        instructor_dbc = joinpath(
            dest_dir, build.output_info.instructor_dir,
            build.output_info.instructor_dbc
        )
        write_version_notebook(instructor_labs, version_notebook, version)
        make_dbc(build, instructor_labs, instructor_dbc)

    copy_slides(build, dest_dir)
    copy_misc_files(build, dest_dir, profile)
    copy_datasets(build, dest_dir)

    if build.bundle_info:
        bundle_course(build, dest_dir, profile)

    # Finally, remove the instructor labs folder and the student labs
    # folder.
    if not build.keep_lab_dirs:
        rm_rf(labs_full_path)
        rm_rf(instructor_labs)

def build_course(build: BuildData,
                 dest_dir: str,
                 overwrite: bool) -> NoReturn:
    """

    :param build:
    :param dest_dir:
    :param overwrite:
    :return:
    """

    if build.course_info.deprecated:
        raise BuildError(
            f'{build.course_info.name} is deprecated and cannot be built.'
        )

    verbose(f'Publishing to "{dest_dir}"')
    if path.isdir(dest_dir):
        if not overwrite:
            raise BuildError(
                f'Directory "{dest_dir}" already exists, and you did not ' +
                'specify overwrite.'
            )

        rm_rf(dest_dir)

    if not build.profiles:
        do_build(build, dest_dir, profile=None)
    else:
        for profile in build.profiles:
            info('')
            info(f"Building profile {profile.name}")
            do_build(build, dest_dir, profile)

    if errors > 0:
        raise BuildError(f"{errors} error(s).")

    print(
        f'\nPublished {build.course_info.name}, ' +
        f'version {build.course_info.version} to {dest_dir}\n'
    )


def dbw(subcommand: str,
        args: Sequence[str],
        capture_stdout: bool = True,
        db_profile: Optional[str] = None) -> Optional[str]:
    """
    Invoke "databricks workspace" with specified arguments.

    :param subcommand:     the "databricks workspace" subcommand
    :param args:           arguments, as a list
    :param capture_stdout: True to capture and return standard output. False
                           otherwise.
    :param db_profile:     The --profile argument for the "databricks" command,
                           if any; None otherwise.

    :return: the string containing standard output, if capture_stdout is True.
             None otherwise.
    :raises DatabricksCliError: if the command fails. If possible, the code
            field will be set
    """
    args = ('workspace', subcommand) + tuple(args)
    return db_cli.databricks(args, capture_stdout=capture_stdout,
                             db_profile=db_profile,
                             verbose=verbosity_is_enabled())


def ensure_shard_path_exists(shard_path: str,
                             db_profile: Optional[str]) -> NoReturn:
    try:
        dbw('ls', [shard_path], db_profile=db_profile)
    except DatabricksCliError as e:
        if e.code == 'RESOURCE_DOES_NOT_EXIST':
            die(f'Shard path "{shard_path}" does not exist.')
        else:
            die(f'Unexpected error with "databricks": {e}')


def ensure_shard_path_does_not_exist(shard_path: str,
                                     db_profile: Optional[str]) -> NoReturn:
    try:
        dbw('ls', [shard_path], db_profile=db_profile)
        die(f'Shard path "{shard_path}" already exists.')
    except DatabricksCliError as e:
        if e.code == 'RESOURCE_DOES_NOT_EXIST':
            pass
        else:
            die(f'Unexpected error with "databricks": {e}')


def expand_shard_path(shard_path: str) -> str:
    if shard_path.startswith('/'):
        return shard_path

    # Relative path. Look for DB_SHARD_HOME environment variable.
    home = os.getenv(DB_SHARD_HOME_VAR)
    if home is not None:
        if len(home.strip()) == 0:
            home = None

    db_config = os.path.expanduser('~/.databrickscfg')
    if home is None:
        if os.path.exists(db_config):
            cfg = ConfigParser()
            cfg.read(db_config)
            try:
                home = cfg.get('DEFAULT', 'home')
            except NoOptionError:
                pass

    if home is None:
        die(f'Shard path "{shard_path}" is relative, but environment ' +
            f'variable {DB_SHARD_HOME_VAR} does not exist or is empty, and ' +
            f'there is no "home" setting in "{db_config}".')

    if shard_path == '':
        shard_path = home
    else:
        shard_path = f'{home}/{shard_path}'

    return shard_path


def notebook_is_transferrable(nb: NotebookData, build: BuildData) -> bool:
    nb_full_path = path.abspath(joinpath(build.source_base, nb.src))

    if not nb.upload_download:
        info(
            f'Skipping notebook "{nb_full_path}": upload_download is disabled.'
        )
        return False

    return True


def get_sources_and_targets(build: BuildData) -> Dict[str, str]:
    """
    Get the list of source notebooks to be uploaded/downloaded and map them
    to their target names on the shard.

    :param build: the build

    :return: A dict of source names to partial-path target names. Each source
             name can map to multiple targets.
    """
    template_data = {
        TARGET_LANG: '',
        NOTEBOOK_TYPE: '',
    }

    profile_subst_pattern = re.compile(r'^(\d*-?)(.*)$')

    def map_notebook_dest(nb):
        template_data2 = {}
        template_data2.update(template_data)
        _, ext = path.splitext(nb.src)
        if ext:
            ext = ext[1:] # skip leading '.'

        template_data2[TARGET_EXTENSION] = ext
        p = path.normpath(
            leading_slashes.sub(
                '', VariableSubstituter(nb.dest).safe_substitute(template_data2)
            )
        )

        if nb.only_in_profile:
            (dir, file) = (path.dirname(p), path.basename(p))
            m = profile_subst_pattern.match(file)
            if not m:
                new_file = '{}-{}'.format(
                    PROFILE_ABBREVIATIONS[nb.only_in_profile], file
                )
            else:
                new_file = '{}{}-{}'.format(
                    m.group(1), PROFILE_ABBREVIATIONS[nb.only_in_profile],
                    m.group(2)
                )
            p = joinpath(dir, new_file)

        return p

    res = {}
    notebooks = [nb for nb in build.notebooks
                 if notebook_is_transferrable(nb, build)]
    leading_slashes = re.compile(r'^/+')

    target_dirs = {}
    for nb in notebooks:
        dest = map_notebook_dest(nb)
        if nb.master.enabled:
            # The destination might be a directory. Count how many notebooks
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

        res[nb_full_path] = res.get(nb_full_path, []) + [dest]

    return res


def check_for_extra_up_down_mappings(notebooks: Dict[str, str]) -> Sequence[Tuple[str, str]]:
    """
    Check the result returned by get_sources_and_targets() for sources that
    map to multiple targets.

    :param notebooks: the result of get_sources_and_targets()

    :return: A sequence of (source, targets) tuples of only those results that
             map to multiple targets. The iterator might be empty.
    """
    res = {}
    for src, targets in list(notebooks.items()):
        if len(targets) == 1:
            continue
        res[src] = targets

    return tuple(res.items())

def upload_notebooks(build: BuildData,
                     shard_path: str,
                     db_profile: Optional[str]) -> NoReturn:
    shard_path = expand_shard_path(shard_path)
    notebooks = get_sources_and_targets(build)

    def do_upload(notebooks: Dict[str, str]) -> NoReturn:
        ensure_shard_path_does_not_exist(shard_path, db_profile)

        with TemporaryDirectory() as tempdir:
            info("Copying notebooks to temporary directory.")
            for nb_full_path, partial_paths in list(notebooks.items()):
                if not path.exists(nb_full_path):
                    warn(f'Skipping nonexistent notebook "{nb_full_path}".')
                    continue
                for partial_path in partial_paths:
                    temp_path = joinpath(tempdir, partial_path)
                    dir = path.dirname(temp_path)
                    mkdirp(dir)
                    verbose(f'Copying "{nb_full_path}" to "{temp_path}"')
                    copy(nb_full_path, temp_path)

            with working_directory(tempdir):
                info(f"Uploading notebooks to {shard_path}")
                try:
                    dbw('import_dir', ['.', shard_path],
                        capture_stdout=False, db_profile=db_profile)
                    info(f"Uploaded {len(notebooks)} notebooks to " +
                         f"{shard_path}.")
                except DatabricksCliError as e:
                    raise UploadDownloadError(f'Upload failed: {e}')

    try:
        do_upload(notebooks)
    except UploadDownloadError as e:
        dbw('rm', [shard_path], capture_stdout=False, db_profile=db_profile)
        die(str(e))

    multiple_mappings = check_for_extra_up_down_mappings(notebooks)
    if len(multiple_mappings) > 0:
        wrap2stdout('\n********')
        wrap2stdout('CAUTION:')
        wrap2stdout('********\n')
        wrap2stdout('Some source files have been copied to multiple destinations!\n')

        for src, targets in multiple_mappings:
            wrap2stdout(
                f'\n"{src}" has been uploaded to multiple places. Only edits ' +
                f'to "{shard_path}/{targets[0]}" will be applied on download.'
            )

        wrap2stdout("\nIf you edit the build file before you run --download, " +
                    "you might lose any edits to those files!")


def download_notebooks(build: BuildData,
                       shard_path: str,
                       db_profile: Optional[str]) -> NoReturn:
    shard_path = expand_shard_path(shard_path)
    notebooks = get_sources_and_targets(build)

    def do_download(notebooks):
        # remote_to_local is assumed to be a 1-1 mapping of remote paths to
        # local paths.
        ensure_shard_path_exists(shard_path, db_profile)
        with TemporaryDirectory() as tempdir:
            info("Downloading notebooks to temporary directory")
            with working_directory(tempdir):
                try:
                    dbw('export_dir', [shard_path, '.'], db_profile=db_profile)
                except DatabricksCliError as e:
                    raise UploadDownloadError(f"Download failed: {e}")

                for local, remotes in list(notebooks.items()):
                    # We only ever download the first one.
                    remote = remotes[0]
                    if not path.exists(remote):
                        warn('Cannot find downloaded version of course ' +
                             f'notebook "{local}".')
                    print(f'"{remote}" -> {local}')
                    # Make sure there's a newline at the end of each file.
                    move(remote, local, ensure_final_newline=True)
                    # Remove any others, so they're not treated as leftovers.
                    for r in remotes[1:]:
                        if path.exists(r):
                            os.unlink(r)

                # Are there any leftovers?
                leftover_files = []
                for root, dirs, files in os.walk('.'):
                    for f in files:
                        leftover_files.append(path.relpath(joinpath(root, f)))
                if len(leftover_files) > 0:
                    warn(
                        f"These files from {shard_path} aren't in the build " +
                        "file and were not copied."
                    )
                    for f in leftover_files:
                        print(f"    {f}")

    # get_sources_and_targets() returns a dict of
    # local-path -> remote-partial-paths. Reverse it. If there are duplicate
    # (remote) keys, keep only the first one. See upload_notebooks()
    remote_to_local = {}
    for local, remotes in list(notebooks.items()):
        # We only ever download the first one.
        remote = remotes[0]
        if remote in remote_to_local:
            die(f'(BUG): Found multiple instances of remote path "{remote}"')

        remote_to_local[remote] = local

    try:
        do_download(notebooks)
    except UploadDownloadError as e:
        die(str(e))

    multiple_mappings = check_for_extra_up_down_mappings(notebooks)
    if len(multiple_mappings) > 0:
        wrap2stdout('\n********')
        wrap2stdout('CAUTION:')
        wrap2stdout('********\n')
        wrap2stdout('Some source files exist more than once in the build file!')

        for src, targets in multiple_mappings:
            wrap2stdout(f'\n"{src}" has ONLY been downloaded from ' +
                        f"{shard_path}/{targets[0]}.")


def print_info(build: BuildData, shell: bool) -> NoReturn:
    """

    :param build:
    :param shell:
    :return:
    """
    if shell:
        print(
            f'COURSE_NAME="{build.name}"; ' +
            f'COURSE_VERSION="{build.course_info.version}"'
        )
    else:
        print(f"Course name:    {build.name}")
        print(f"Course version: {build.course_info.version}")


def validate_build(build: BuildData) -> BuildData:
    """
    :param build:
    :return:
    :raises BuildConfigError: validation failed, and errors were printed
    """
    # TODO: Path joins here duplicate logic elsewhere. Consolidate.
    errors = 0
    error_prefix = "ERROR: "
    wrapper = EnhancedTextWrapper(subsequent_indent=' ' * len(error_prefix))
    build_file_dir = path.dirname(path.abspath(build.build_file_path))

    def complain(msg):
        print(wrapper.fill(error_prefix + msg))

    def rel_to_build(src):
        return joinpath(build_file_dir, src)

    def rel_to_src_base(src):
        return joinpath(build.source_base, src)

    if not path.exists(build.source_base):
        complain(f'src_base "{path.abspath(build.source_base)}" does not exist.')
        errors += 1

    headings = set()
    footers = set()

    new_notebooks = []

    for notebook in build.notebooks:
        src_path = rel_to_src_base(notebook.src)
        if not path.exists(src_path):
            complain(f'Notebook "{src_path}" does not exist.')
            errors += 1
            continue

        if os.stat(src_path).st_size == 0:
            complain(f'Notebook "{src_path}" is an empty file. Ignoring it.')
            continue

        # Attempt to parse the notebook. If it has no cells, ignore it.
        try:
            nb = parse_source_notebook(src_path, encoding='UTF-8')
            if len(nb.cells) == 0:
                complain(f'Notebook "{src_path}" has no cells. Ignoring it.')
                continue
        except NotebookError as e:
            complain(f'Notebook "{src_path}" cannot be parsed: {e}')
            errors += 1
            continue

        new_notebooks.append(notebook)

        master = notebook.master
        if master and master.enabled:
            if master.heading.enabled and (master.heading.path is not None):
                headings.add(rel_to_build(master.heading.path))

            if master.footer.enabled and (master.footer.path is not None):
                footers.add(rel_to_build(master.footer.path))

    build.notebooks = new_notebooks

    for h in headings:
        if not path.exists(h):
            complain(f'Notebook heading "{h}" does not exist.')
            errors += 1

    for f in footers:
        if not path.exists(f):
            complain(f'Notebook footer "{f}" does not exist.')
            errors += 1

    for misc in build.misc_files:
        src_path = rel_to_build(misc.src)
        if not path.exists(src_path):
            complain(f'misc_file "{src_path}" does not exist.')
            errors += 1
        if misc.only_in_profile and (not build.profiles):
            complain(
                f'misc file "{src_path}" specifies only_in_profile, but ' +
                'profiles are not enabled.'
            )
            errors += 1

    if build.slides:
        for slide in build.slides:
            src_path = rel_to_src_base(slide.src)
            if not path.exists(src_path):
                complain(f'Slide "{src_path}" does not exist.')
                errors += 1

    if build.datasets:
        for dataset in build.datasets:
            src_path = joinpath(build.course_directory, dataset.src)
            if not path.exists(src_path):
                complain(f'Dataset "{src_path}" does not exist.')
                errors += 1

    if build.markdown and build.markdown.html_stylesheet:
        if not path.exists(build.markdown.html_stylesheet):
            complain(
                f'markdown.html_stylesheet "{build.markdown.html_stylesheet}" '+
                'does not exist.'
            )
            errors +=1

    if errors == 1:
        print("\n*** One error.")
    elif errors > 1:
        print(f"\n*** {errors} errors.")

    if errors > 0:
        raise BuildConfigError("Build file validation failure.")

    return build


def load_and_validate(build_file: str) -> BuildData:
    build = load_build_yaml(build_file)
    return validate_build(build)


def init_verbosity(verbose: bool) -> NoReturn:
    if verbose:
        set_verbosity(True, verbose_prefix='bdc: ')
    else:
        set_verbosity(False, verbose_prefix='')


def default_output_directory_for_build(build: BuildData) -> str:
    return joinpath(os.getenv("HOME"), "tmp", "curriculum",
                    build.course_id)

# ---------------------------------------------------------------------------
# Exported functions
# ---------------------------------------------------------------------------

def bdc_check_build(build_file: str, verbose: bool = False) -> NoReturn:
    """
    :param build_file:
    :param verbose:
    :return:
    """
    init_verbosity(verbose)
    _ = load_and_validate(build_file)
    if errors == 0:
        print('\nNo errors.')
    else:
        # Error messages already printed.
        raise BuildError(f'There are problems with "{build_file}".')


def bdc_get_notebook_paths(build_file: str) -> Sequence[str]:
    """
    Get the paths of all source notebooks in a build file. Notebooks that
    are used multiple times are only listed once.

    :param build_file: the build file to load

    :return: the notebook paths, as absolute paths
    """
    build = load_and_validate(build_file)
    return sorted(list(set([joinpath(build.source_base, notebook.src)
                       for notebook in build.notebooks])))


def bdc_list_notebooks(build_file: str) -> NoReturn:
    """
    Print the paths of notebooks in a build file to standard output. Notebooks
    that appear multiple times in a build are only listed once.

    :param build_file: the build out.
    :return: Nothing
    """
    for p in bdc_get_notebook_paths(build_file):
        print(p)


def bdc_print_info(build_file: str, shell_format: bool = False) -> NoReturn:
    """
    Display information about the build file to standard output.

    :param build_file:    the path to the build file
    :param shell_format:  whether to print the info as shell assignments (True)
                          or in human-readable form (False).
    :return: Nothing
    """
    build = load_and_validate(build_file)
    print_info(build, shell_format)


def bdc_upload(build_file: str,
               shard_path: str,
               databricks_profile: Optional[str] = None,
               verbose: bool = False) -> NoReturn:
    """
    Upload a course's source notebooks to Databricks.

    :param build_file:          the path to the build file for the course
    :param shard_path:          the Databricks path to which to upload them
    :param databricks_profile:  the Databricks authentication profile to use
    :param verbose:             whether or not to display verbose messages

    :return: Nothing
    """
    init_verbosity(verbose)
    build = load_and_validate(build_file)
    upload_notebooks(build, shard_path, databricks_profile)


def bdc_download(build_file: str,
                 shard_path: str,
                 databricks_profile: Optional[str] = None,
                 verbose: bool = False) -> NoReturn:
    """
    Download a course's source notebooks from Databricks and copy them back
    over top of the notebooks on the local disk.

    :param build_file:          the path to the build file for the course
    :param shard_path:          the Databricks path from which to download them
    :param databricks_profile:  the Databricks authentication profile to use
    :param verbose:             whether or not to display verbose messages

    :return: Nothing
    """
    init_verbosity(verbose)
    build = load_and_validate(build_file)
    download_notebooks(build, shard_path, databricks_profile)


def bdc_output_directory_for_build(build_file: str) -> str:
    """
    Determine the default output directory for a particular course.

    :param build_file: the build file for the course

    :return: the path to the output directory
    """
    build = load_and_validate(build_file)
    return default_output_directory_for_build(build)


def bdc_build_course(build_file: str,
                     dest_dir: str,
                     overwrite: bool,
                     verbose: bool = False) -> NoReturn:
    """
    Build a course.

    :param build_file: the path to the build file
    :param dest_dir:   the destination directory for the build, or None to use
                       the default
    :param overwrite:  If the destination directory exists already, and this
                       parameter is True, then the destination directory will
                       be recursively removed before the build is run. If the
                       directory is there and this parameter is False, the
                       function will raise an exception.
    :param verbose:    whether or not to display verbose messages

    :return: Nothing
    """
    init_verbosity(verbose)
    build = load_and_validate(build_file)
    if not dest_dir:
        dest_dir = joinpath(os.getenv("HOME"), "tmp", "curriculum",
                            build.course_id)
    build_course(build, dest_dir, overwrite)


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def main():

    opts = parse_args()

    course_config = opts['BUILD_YAML'] or DEFAULT_BUILD_FILE
    if not os.path.exists(course_config):
        die(f'{course_config} does not exist.')

    try:
        if opts['--check']:
            bdc_check_build(course_config)
        elif opts['--info']:
            bdc_print_info(course_config, opts['--shell'])
        elif opts['--list-notebooks']:
            bdc_list_notebooks(course_config)
        elif opts['--upload']:
            bdc_upload(course_config, opts['SHARD_PATH'], opts['--dprofile'],
                       opts['--verbose'])
        elif opts['--download']:
            bdc_download(course_config, opts['SHARD_PATH'], opts['--dprofile'],
                         opts['--verbose'])
        else:
            bdc_build_course(course_config, opts['--dest'], opts['--overwrite'],
                             opts['--verbose'])

    except BuildConfigError as e:
        die(f'Error in "{course_config}": {e}')
    except BuildError as e:
        die(str(e))
    except KeyboardInterrupt:
        die(f'\n*** Interrupted.')

if __name__ == '__main__':
    main()
