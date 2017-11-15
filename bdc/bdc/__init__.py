#!/usr/bin/env python

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from builtins import (bytes, dict, int, list, object, range, str, ascii,
                      chr, hex, input, next, oct, open, pow, round, super,
                      filter, map, zip)

from future import standard_library
standard_library.install_aliases()

import sys

if sys.version_info >= (3,):
    from configparser import ConfigParser
else:
    from ConfigParser import ConfigParser
from collections import namedtuple
import os
from os import path
from string import Template
import shutil
import contextlib
import markdown2
import codecs
import re
import master_parse
from grizzled.file import eglob

# We're using backports.tempfile, instead of tempfile, so we can use
# TemporaryDirectory in both Python 3 and Python 2. tempfile.TemporaryDirectory
# was added in Python 3.2.
from backports.tempfile import TemporaryDirectory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "1.7.0"

DEFAULT_BUILD_FILE = 'build.yaml'
PROG = os.path.basename(sys.argv[0])

USAGE = ("""
{0}, version {1}

Usage:
  {0} (--version)
  {0} (-h | --help)
  {0} [(-o | --overwrite)] [(-v | --verbose)] MASTER_CFG [BUILD_YAML]
  {0} --list-notebooks [BUILD_YAML]

MASTER_CFG is the build tool's master configuration file.
BUILD_YAML is the build file for the course to be built. Defaults to {2}

Options:
  -h --help       Show this screen.
  -o --overwrite  Overwrite the destination directory, if it exists.
  -v --verbose    Print what's going on to standard output.
  --version       Display version and exit.

""".format(PROG, VERSION, DEFAULT_BUILD_FILE))

INSTRUCTOR_FILES_SUBDIR = "InstructorFiles" # instructor files subdir
INSTRUCTOR_LABS_SUBDIR = path.join(INSTRUCTOR_FILES_SUBDIR, "Instructor-Labs")
INSTRUCTOR_LABS_DBC = path.join(INSTRUCTOR_FILES_SUBDIR, "Instructor-Labs.dbc")
STUDENT_FILES_SUBDIR = "StudentFiles"    # student files subdir
STUDENT_LABS_SUBDIR = path.join(STUDENT_FILES_SUBDIR, "Labs")
STUDENT_LABS_DBC = path.join(STUDENT_FILES_SUBDIR, "Labs.dbc")
SLIDES_SUBDIR = path.join(INSTRUCTOR_FILES_SUBDIR, "Slides")
DATASETS_SUBDIR = path.join(STUDENT_FILES_SUBDIR, "Datasets")
INSTRUCTOR_NOTES_SUBDIR = path.join(INSTRUCTOR_FILES_SUBDIR, "InstructorNotes")
TARGET_LANG = 'target_lang'

# EXT_LANG is used when parsing the YAML file.
EXT_LANG = {'.py':    'Python',
            '.ipynb': 'ipython',
            '.r':     'R',
            '.scala': 'Scala',
            '.sql':   'SQL'}

# LANG_EXT: Mapping of language (in lower case) to extension
LANG_EXT = dict([(v.lower(), k) for k, v in EXT_LANG.items()])

# This is the HTML template into which the converted Markdown will be inserted.
# There are several substitution parameters:
#
# $title - the document's title
# $css   - where the stylesheet is inserted
# $body  - where the converted Markdown HTML goes
DEFAULT_HTML_TEMPLATE = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>$title</title>
    <style type="text/css">
$css
    </style>
  </head>
  <body>
$body
  </body>
</html>
"""

DEFAULT_CSS = """body {
  font-family: sans-serif;
  margin-left: 0.75in;
  margin-right: 0.5in;
}
tt, pre, code {
  font-family: Consolas, Menlo, monospace;
}
table thead tr th {
  border-bottom: 1px solid #ccc;
}
table tbody tr:nth-child(even) {
  background: #ccc;
}
table tbody tr:nth-child(odd) {
  background: #fff;
}
tr td {
  padding: 5px;
}
h1, h2, h3, h4, h5, h6 {
  font-family: Newslab, sans-serif;
  margin-left: -0.25in;
}
h3 {
  font-style: italic;
}
h4 {
  text-decoration: underline;
}
"""

# Always generate Databricks notebooks.
MASTER_PARSE_DEFAULTS = {
    'enabled':          False,
    'python':           True,
    'r':                False,
    'scala':            True,
    'sql':              False,
    'answers':          True,
    'encoding_in':      'UTF-8',
    'encoding_out':     'UTF-8'
}

ANSWERS_NOTEBOOK_PATTERN = re.compile('^.*_answers\..*$')

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

html_template = Template(DEFAULT_HTML_TEMPLATE)
be_verbose = False
errors = 0

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

Config = namedtuple('Config', ('gendbc', 'build_directory'))


class BuildError(Exception):
    def __init__(self, message):
        self.message = message


class ConfigError(BuildError):
    def __init__(self, message):
        self.message = message


class NotebookData(object):
    def __init__(self,
                 src,
                 dest,
                 run_test=False,
                 master=None):
        self.src = src
        self.dest = dest
        self.run_test = run_test
        self.master = master or dict(MASTER_PARSE_DEFAULTS)

    def master_enabled(self):
        '''
        Determine whether master notebook processing is enabled for this
        notebook.

        :return: true or false
        '''
        return self.master and self.master.get('enabled', False)

    def __str__(self):
        return "NotebookData(src='{0}', dest='{1}', master={2})".format(
            self.src, self.dest, self.master
        )

    def __repr__(self):
        return self.__str__()

MiscFileData = namedtuple('MiscFileData', ('src', 'dest'))
SlideData = namedtuple('SlideData', ('src', 'dest'))
DatasetData = namedtuple('DatasetData', ('src', 'dest', 'license', 'readme'))
CourseInfo = namedtuple('CourseInfo', ('name', 'version', 'class_setup',
                                       'schedule', 'instructor_prep',
                                       'deprecated'))
MarkdownInfo = namedtuple('MarkdownInfo', ('html_stylesheet',))


class BuildData(object):
    def __init__(self,
                 build_file_path,
                 source_base,
                 course_info,
                 notebooks,
                 slides,
                 datasets,
                 misc_files,
                 keep_lab_dirs,
                 notebook_heading_path,
                 add_heading,
                 markdown_cfg):
        self.build_file_path = build_file_path
        self.course_directory = path.dirname(build_file_path)
        self.notebooks = notebooks
        self.course_info = course_info
        self.source_base = source_base
        self.slides = slides
        self.datasets = datasets
        self.markdown = markdown_cfg
        self.misc_files = misc_files
        self.keep_lab_dirs = keep_lab_dirs
        self.notebook_heading_path = notebook_heading_path
        self.add_heading = add_heading

    @property
    def name(self):
        return self.course_info.name

    @property
    def course_id(self):
        '''
        The course ID, which is a combination of the course name and the
        version, suitable for use as a directory name.

        :return: the course ID string
        '''
        return '{0}-{1}'.format(self.name, self.course_info.version)

    def __str__(self):
        return (
            'BuildData(course_info={0}, notebooks={1}, source_base={2}, ' +
            'slides={3}, datasets={4}, markdown={5}, file_path={6}, ' +
            'misc_files={7}'
        ).format(
            self.course_info, self.notebooks, self.source_base,
            self.slides, self.datasets, self.markdown, self.build_file_path,
            self.misc_files
        )

    def __repr__(self):
        return str(self)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def verbose(msg):
    """Conditionally emit a verbose message."""
    if be_verbose:
        print("{0}: {1}".format(PROG, msg))


def error(msg):
    """
    Emit a message to standard error.

    :param msg: the message
    """
    global errors
    errors += 1
    sys.stderr.write("***\n")
    sys.stderr.write(msg + "\n")
    sys.stderr.write("***\n")


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
    """
    import yaml
    verbose("Loading {0}...".format(yaml_file))
    with open(yaml_file, 'r') as y:
        contents = yaml.safe_load(y)

    def bool_value(s):
        if isinstance(s, bool):
            return s

        sl = s.lower()
        if sl in ('t', 'true', '1', 'yes'):
            return True
        elif sl in ('f', 'false', '0', 'no'):
            return False
        else:
            raise ConfigError('Bad boolean value: "{0}"'.format(s))

    def bool_field(d, key, default=False):
        val = d.get(key, default)
        return bool_value(val)

    def required(d, key, where):
        v = d.get(key)
        if v is None:
            raise ConfigError(
                '{0}: Missing required "{1}" value in "{2}".'.format(
                    yaml_file, key, where
                )
            )
        return v

    def subst(dest, src, allow_lang=True):
        base_with_ext = path.basename(src)
        (base_no_ext, ext) = path.splitext(base_with_ext)
        fields = {
            'basename':     base_no_ext,
            'extension':    ext,
            'filename':     base_with_ext,
            # Note: ${target_lang} is substituted by process_master_notebook,
            # so it has to be explicitly preserved here, if it exists.
            TARGET_LANG:   '${' + TARGET_LANG + '}',
        }
        if allow_lang:
            fields['lang'] = EXT_LANG.get(ext, "???")

        return Template(dest).substitute(fields)

    def parse_notebook(obj):
        src = required(obj, 'src', 'notebooks section')
        dest = subst(required(obj, 'dest', 'notebooks section'), src)
        if bool_field(obj, 'skip'):
            verbose('Skipping notebook {0}'.format(src))
            return None

        master = dict(MASTER_PARSE_DEFAULTS)
        master.update(obj.get('master', {}))
        extra_keys = master.keys() - MASTER_PARSE_DEFAULTS.keys()
        if len(extra_keys) > 0:
            raise ConfigError(
                ('Notebook {0}: Unknown fields in "master" section: {1}'.format(
                    src, ', '.join(sorted(extra_keys))
                ))
            )

        _, dest_ext = os.path.splitext(dest)
        if master and master.get('enabled', False):
            if dest_ext:
                raise ConfigError(
                    ('Notebook {0}: When "master" is enabled, "dest" must be ' +
                    'a directory.').format(src)
                )
        else:
            _, src_ext = os.path.splitext(src)
            if (not dest_ext) or (dest_ext != src_ext):
                raise ConfigError(
                    ('Notebook {0}: "master" is disabled, so "dest" should ' +
                     'have extension "{1}".').format(src, src_ext)
                )
            # Check for the presence of ${target_lang} by substituting something
            # that should never appear in a destination, then searching for it.
            token = u'\u2122$$$$$$$$$$\u2122'
            d = Template(dest).safe_substitute({TARGET_LANG: token})
            if token in d:
                raise ConfigError(
                    ('Notebook {0}: ${1} found in "dest", but "master" is disabled'.
                      format(src, TARGET_LANG))
                )

        return NotebookData(
            src=src,
            dest=dest,
            master=master,
            run_test=bool_value(obj.get('run_test', 'false'))
        )

    def parse_slide(obj):
        src = required(obj, 'src', 'notebooks')
        dest = required(obj, 'dest', 'notebooks')
        if bool_field(obj, 'skip'):
            verbose('Skipping slide {0}'.format(src))
            return None
        else:
            return SlideData(
                src=src,
                dest=subst(dest, src, allow_lang=False)
            )

    def parse_misc_file(obj):
        src = required(obj, 'src', 'misc_files')
        dest = required(obj, 'dest', 'misc_files')
        if bool_field(obj, 'skip'):
            verbose('Skipping file {0}'.format(src))
            return None
        else:
            return MiscFileData(
                src=src,
                dest=subst(dest, src, allow_lang=False)
            )

    def parse_dataset(obj):
        src = required(obj, 'src', 'notebooks')
        dest = required(obj, 'dest', 'notebooks')
        if bool_field(obj, 'skip'):
            verbose('Skipping data set {0}'.format(src))
            return None
        else:
            src_dir = path.dirname(src)
            return DatasetData(
                src=src,
                dest=subst(dest, src, allow_lang=False),
                license=path.join(src_dir, 'LICENSE.md'),
                readme=path.join(src_dir, 'README.md')
            )

    def parse_file_section(section, parse):
        # Use the supplied parse function to parse each element in the
        # supplied section, filtering out None results from the function.
        # Convert the entire result to a tuple.
        return tuple(
            filter(lambda o: o != None, [parse(i) for i in section])
        )

    def parse_markdown(obj):
        if obj:
            stylesheet = obj.get('html_stylesheet')
        else:
            stylesheet = None
        return MarkdownInfo(html_stylesheet=stylesheet)

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
        deprecated=course_info_cfg.get('deprecated', False)
    )

    src_base = required(contents, 'src_base', 'build')
    build_yaml_full = path.abspath(yaml_file)
    build_yaml_dir = path.dirname(build_yaml_full)
    src_base = path.abspath(path.join(build_yaml_dir, src_base))

    if slides_cfg:
        slides = parse_file_section(slides_cfg, parse_slide)
    else:
        slides = None

    if datasets_cfg:
        datasets = parse_file_section(datasets_cfg, parse_dataset)
    else:
        datasets = None

    if misc_files_cfg:
        misc_files = parse_file_section(misc_files_cfg, parse_misc_file)
    else:
        misc_files = None

    if notebooks_cfg:
        notebooks = parse_file_section(notebooks_cfg, parse_notebook)
    else:
        notebooks = None

    notebook_heading = contents.get('notebook_heading', {})

    data = BuildData(
        build_file_path=build_yaml_full,
        course_info=course_info,
        notebooks=notebooks,
        slides=slides,
        datasets=datasets,
        source_base=src_base,
        misc_files=misc_files,
        keep_lab_dirs=bool_field(contents, 'keep_lab_dirs'),
        add_heading=notebook_heading.get('enabled', True),
        notebook_heading_path=notebook_heading.get('path'),
        markdown_cfg=parse_markdown(contents.get('markdown'))
    )

    return data


def load_config(config_path):
    """
    Load the master configuration file for the build tool. Returns a
    Config object (see above). Throws a ConfigError on error.
    """
    p = ConfigParser()
    p.read(config_path)

    def required_path(section, option):
        val = path.expanduser(p.get(section, option))
        if val is None:
            raise ConfigError(
                'Missing required "{0}.{1}" value in configuration'.format(
                    section, option
                )
            )
        return val

    def must_be_absolute(section, option, path):
        if not os.path.isabs(path):
            raise ConfigError(
                'Section [{0}]: Option {1} is not an absolute path.'.format(
                    section, option
                )
            )
        return path

    opts = [
        must_be_absolute('main', i, required_path('main', i))
        for i in ('gendbc', 'build_directory')
    ]

    return Config(*opts)


def parse_args():
    """
    Parse the command line parameters.
    """
    from docopt import docopt
    return docopt(USAGE, version=VERSION)


@contextlib.contextmanager
def working_directory(path):
    """
    Simple context manager that runs the code under "with" in a specified
    directory, returning to the original directory when the "with" exits.
    """
    prev = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(prev)


def ensure_parent_dir_exists(target):
    dir = path.dirname(target)
    if not path.exists(dir):
        verbose('mkdir -p "{0}"'.format(dir))
        os.makedirs(dir)


def move(src, dest):
    """
    Move a source file to a new destination, ensuring that any intermediate
    destinations are created.

    :param src:   src file
    :param dest:  destination file
    :return: None
    """
    if not path.exists(src):
        raise ConfigError('"{0}" does not exist.'.format(src))
    src = path.abspath(src)
    dest = path.abspath(dest)
    ensure_parent_dir_exists(dest)
    verbose('mv "{0}" "{1}"'.format(src, dest))
    shutil.move(src, dest)

def copy(src, dest):
    """
    Copy a source file to a destination file, honoring the --verbose
    command line option and creating any intermediate destination
    directories.

    :param src:   src file
    :param dest:  destination file
    :return: None
    """
    if not path.exists(src):
        raise ConfigError('"{0}" does not exist.'.format(src))
    src = path.abspath(src)
    dest = path.abspath(dest)
    ensure_parent_dir_exists(dest)
    verbose('cp "{0}" "{1}"'.format(src, dest))
    shutil.copy2(src, dest)


def markdown_to_html(md, html_out, stylesheet=None):
    """
    Convert a Markdown file to HTML, writing it to the specified HTML file.
    If the stylesheet is specified, it is inserted.
    """
    verbose('Generating "{0}" from "{1}"'.format(html_out, md))
    with codecs.open(md, mode='r', encoding='UTF-8') as input:
        text = input.read()
        body = markdown2.markdown(text, extras=['fenced-code-blocks',
                                                'tables'])
        if not stylesheet:
            stylesheet = DEFAULT_CSS
        with codecs.open(html_out, mode='w', encoding='UTF-8') as output:
            output.write(
                html_template.substitute(
                    body=body,
                    title=path.basename(md),
                    css=stylesheet
                )
            )


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
        html_out = path.join(path.dirname(target_full),
                                src_simple + '.html')
        markdown_to_html(src_file, html_out, build.markdown.html_stylesheet)


def process_master_notebook(dest_root, notebook, src_path, add_heading,
                            notebook_heading_path):
    """
    Process a master notebook.

    :param dest_root:  top-level target directory for build
    :param notebook:   the notebook data from the build YAML
    :param src_path:   the pre-calculated path to the source notebook
    :param dest_path:  the path to the target directory, calculated from
                       dest_root and notebook.dest
    :return: None
    """
    verbose("notebook={0}\ndest_root={1}".format(notebook, dest_root))

    def move_master_notebooks(master, temp_output_dir):
        """
        Move master-parsed notebooks.

        :param master:           the master notebook configuration data
        :param temp_output_dir:  the temporary output directory
        """
        # See if we have to move the notebooks to other paths.
        for lang in set(EXT_LANG.values()):
            lc_lang = lang.lower()
            if not master.get(lc_lang):
                continue

            # This language is desired. Calculate the path. The path is
            # <dest_root> + <notebook.dest> + file
            #
            # <notebook.dest> can have the language in it. If it's not there,
            # we put the language at the beginning.
            lang_dir = lc_lang.capitalize()
            dest_subst = Template(notebook.dest).safe_substitute(
                {TARGET_LANG: lang_dir}
            )

            if dest_subst == notebook.dest:
                dest_subst = path.join(lang_dir, notebook.dest)

            # Get the file name extension for the language. Note that this
            # extension INCLUDES the ".".
            lang_ext = LANG_EXT[lc_lang]

            # The master parse tool created <notebook-basename>/<lang>/*
            # in the temporary directory. The following recursive glob pattern
            # will make finding the files simple. In this glob pattern, {0} is
            # the notebook type (e.g., "_answers"), and {1} is the file
            # extension (e.g., ".py")
            glob_template = "**/*_{0}*{1}"

            # Copy all answers notebooks and exercises notebooks to the student
            # labs directory. Copy all instructor notebooks to the instructor
            # labs directory.

            student_dir = path.join(dest_root, STUDENT_LABS_SUBDIR)
            instructor_dir = path.join(dest_root, INSTRUCTOR_LABS_SUBDIR)

            types_and_targets = [
                ("exercises", student_dir),
                ("instructor", instructor_dir),
            ]

            if master['answers']:
                types_and_targets.append(
                    ("answers", student_dir)
                )

            base, _ = path.splitext(path.basename(notebook.src))
            mp_notebook_dir = path.join(temp_output_dir, base, lc_lang)


            for type, target_dir in types_and_targets:
                # Use a recursive glob pattern to find all matching notebooks.
                # Note that eglob returns a generator.
                copied = 0
                glob_pattern = glob_template.format(type, lang_ext)
                matches = eglob(glob_pattern, mp_notebook_dir)

                for f in matches:
                    target = path.join(target_dir, dest_subst, path.basename(f))
                    copy(f, target)
                    copied += 1

                if copied == 0:
                    error('Found no generated {0} {1} notebooks for "{2}"!'.
                        format(lang, type, notebook.src)
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
                scala=master['scala'],
                python=master['python'],
                r=master['r'],
                sql=master['sql'],
                instructor=True,
                exercises=True,
                answers=master['answers'],
                notebook_heading_path=notebook_heading_path,
                encoding_in=master['encoding_in'],
                encoding_out=master['encoding_out'],
                enable_verbosity=be_verbose,
                add_heading=add_heading
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
        src_path = path.join(build.source_base, notebook.src)
        if notebook.master_enabled():
            process_master_notebook(
                dest_root=dest_root,
                notebook=notebook,
                src_path=src_path,
                notebook_heading_path=build.notebook_heading_path,
                add_heading=build.add_heading
            )
        else:
            dest_path = path.join(labs_dir, notebook.dest)
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
                s = path.join(dirpath, f)
                t = path.join(dest_root, INSTRUCTOR_NOTES_SUBDIR, rel_dir, f)
                verbose("Copying {0} to {1}".format(s, t))
                copy_info_file(s, t, build)
                continue


def make_dbc(config, build, labs_dir, dbc_path):
    """
    Create a DBC file from the labs.
    """
    wd = path.dirname(labs_dir)
    with working_directory(wd):
        simple_labs_dir = path.basename(labs_dir)
        if be_verbose:
            cmd = "{0} {1} {2} {3} {4} {5}".format(
                config.gendbc, "-v", "-f", build.course_id,
                simple_labs_dir, dbc_path
            )
        else:
            cmd = "{0} {1} {2} {3} {4}".format(
                config.gendbc, "-f", build.course_id, simple_labs_dir, dbc_path
            )

        verbose("\n*** In {0}:\n{1}\n".format(wd, cmd))
        rc = os.system(cmd)
        if rc != 0:
            raise BuildError("Failed to create DBC: " + cmd)


def copy_slides(build, dest_root):
    """
    Copy the slides (if any).
    """
    if build.slides:
        for f in build.slides:
            src = path.join(build.source_base, f.src)
            dest = path.join(dest_root, SLIDES_SUBDIR, f.dest)
            copy(src, dest)


def copy_misc_files(build, dest_root):
    """
    Copy the miscellaneous files (if any).
    """
    if build.misc_files:
        for f in build.misc_files:
            s = path.join(build.course_directory, f.src)
            t = path.join(dest_root, f.dest)
            copy_info_file(s, t, build)


def copy_datasets(build, dest_root):
    """
    Copy the datasets (if any).
    """
    if build.datasets:
        for ds in build.datasets:
            for i in (ds.src, ds.license, ds.readme):
                source = path.join(build.course_directory, i)
                target = path.join(dest_root, DATASETS_SUBDIR, ds.dest,
                                   path.basename(i))
                copy(source, target)


def remove_empty_subdirectories(directory):
    for dirpath, _, _ in os.walk(directory, topdown=False):
        if len(os.listdir(dirpath)) == 0:
            verbose("Deleting empty directory {0}".format(dirpath))
            os.rmdir(dirpath)


def build_course(opts, build, bdc_config):
    config = load_config(bdc_config)
    if build.course_info.deprecated:
        die('{0} is deprecated and cannot be built.'.format(
            build.course_info.name
        ))

    dest_dir = path.join(config.build_directory, build.course_id)
    verbose('Publishing to "{0}"'.format(dest_dir))
    if path.isdir(dest_dir):
        if not opts['--overwrite']:
            die(('Directory "{0}" already exists, and you did not ' +
                 'specify --overwrite.').format(dest_dir))

        shutil.rmtree(dest_dir)

    for d in [INSTRUCTOR_FILES_SUBDIR, STUDENT_FILES_SUBDIR]:
        os.makedirs(path.join(dest_dir, d))

    labs_full_path = path.join(dest_dir, STUDENT_LABS_SUBDIR)
    copy_notebooks(build, labs_full_path, dest_dir)
    copy_instructor_notes(build, dest_dir)
    make_dbc(config, build, labs_full_path, path.join(dest_dir, STUDENT_LABS_DBC))
    instructor_labs = path.join(dest_dir, INSTRUCTOR_LABS_SUBDIR)
    if os.path.exists(instructor_labs):
        instructor_dbc = path.join(dest_dir, INSTRUCTOR_LABS_DBC)
        make_dbc(config, build, instructor_labs, instructor_dbc)
    copy_slides(build, dest_dir)
    copy_misc_files(build, dest_dir)
    copy_datasets(build, dest_dir)

    # Finally, remove the instructor labs folder and the student labs
    # folder.
    if not build.keep_lab_dirs:
        shutil.rmtree(labs_full_path)
        shutil.rmtree(instructor_labs)

    if errors > 0:
        raise BuildError("{0} error(s).".format(errors))

    print("\nPublished {0}, version {1} to {2}\n".format(
        build.course_info.name, build.course_info.version, dest_dir
    ))


def list_notebooks(build):
    for notebook in build.notebooks:
        src_path = path.join(build.source_base, notebook.src)
        print(src_path)

# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def main():
    opts = parse_args()
    global be_verbose
    be_verbose = opts['--verbose']

    bdc_config = opts['MASTER_CFG']
    course_config = opts['BUILD_YAML'] or DEFAULT_BUILD_FILE

    try:
        build = load_build_yaml(course_config)
        if opts['--list-notebooks']:
            list_notebooks(build)
        else:
            build_course(opts, build, bdc_config)

    except ConfigError as e:
        die('Error in "{0}": {1}'.format(course_config, e.message))
    except BuildError as e:
        die(e.message)

if __name__ == '__main__':
    main()
