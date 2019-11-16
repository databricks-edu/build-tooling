#!/usr/bin/env python
'''
This is the "course" curriculum development workflow tool. Run "course help"
for complete documentation.
'''

import os
import sys
import bdc
import re
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from termcolor import colored
from string import Template as StringTemplate
import functools
from subprocess import Popen
from db_edu_util import (die, error, warn, debug, info, set_debug, databricks,
                         working_directory)
from db_edu_util.databricks import DatabricksError
from typing import (Generator, Sequence, Pattern, NoReturn, Optional, Any,
                    Dict, TextIO)

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

VERSION = '2.8.0'
PROG = os.path.basename(sys.argv[0])

CONFIG_PATH = os.path.expanduser("~/.databricks/course.cfg")

USER = os.environ['USER'] # required
PAGER_DEFAULT = 'less --RAW-CONTROL-CHARS'
EDITOR_DEFAULT = 'open -a textedit'
SOURCE_DEFAULT = '_Source'
TARGET_DEFAULT = '_Build'
AWS_PROFILE_DEFAULT = 'default'
DB_PROFILE_DEFAULT = 'DEFAULT'
COURSE_REPO_DEFAULT = os.path.expanduser('~/repos/training')
DB_CONFIG_PATH_DEFAULT = os.path.expanduser('~/.databrickscfg')
OPEN_DIR_DEFAULT = 'open' # Mac-specific, but can be configured.
SELF_PACED_PATH_DEFAULT = os.path.join('courses', 'Self-Paced')

USAGE = '''
{0}, version {VERSION}

USAGE

  {0} (-h | --help | help | usage)
  {0} <subcommand> ...
  
DESCRIPTION

  "course" is a build workflow tool, sitting on top of "bdc".
   
  Many subcommands can be chained. For instance:
  
      course upload build
      course work-on Delta build

  Some commands end the chain, because they consume all remaining arguments.
  Examples include "sed" and "xargs".
  
  Some subcommands require a course name. You can set the default course name
  via:
   
      course work-on coursename
       
  Some subcommands honor a command line override via --name. This override
  does not change the default stored in the configuration. You can also
  temporarily override the stored course name by setting COURSE_NAME in the
  environment.
  
  You can change the stored course name in three ways:
  
  1) Use "work-on": course work-on Delta
  2) Use "set": course set COURSE_NAME=ETL-Part-2
  3) Manually edit the configuration file, "{CONFIG_PATH}"
  
  Some commands don't work if you're running the tool inside a Docker container.
  If you use the established Docker aliases, "course" will be able to tell that
  it's running inside Docker, and it'll refuse to run those commands. See below
  for the commands that aren't Docker-able.
      
SUBCOMMANDS

  The various "course" commands are listed below. Those marked with "*"
  will NOT work in a Docker container.

  {0} (--help, -h, help) Show the full help page (this output)
  {0} (--version, -V)    Display version and exit
  {0} toolversions       Display course, bdc, gendbc, and master_parse versions
                         and exit.
  {0} install-tools      Deprecated. Use: curl -L https://git.io/fhaLg | bash
  {0} work-on <name>     Specify and remember the course to build, 
                         upload, etc.
  {0} which              Print the name of the current course.
  {0} download           Download from SOURCE
  {0} build              Build course from local files and upload built
  {1}                    artifacts to Databricks.
  {0} build-local        Build course from local files without 
  {1}                    uploading artifacts.
  {0} upload             Upload local sources (from your Git repo) to 
  {1}                    SOURCE.
  {0} upload-built       Upload built artifacts. Assumes you already
  {1}                    ran "{0} buildlocal".
  {0} clean              Remove TARGET (built artifact) from Databricks            
  {0} clean-source       Remove SOURCE (built artifact) from Databricks
  {0} status             Run a "git status" on the local repository 
  {1}                    clone.
  {0} diff               Run a "git diff" on the local repository,
  {1}                    clone and pipe the output through PAGER. 
  {1}                    PAGER isn't set, the diff output is just
  {1}                    dumped to standard output.
  {0} difftool         * Run "git difftool" (with "opendiff") on
  {1}                    the repository clone. 
  {0} tag                Tag the Git repo with the current course and version.
  {1}                    Applies the tag to the top-most commit on the current
  {1}                    repo branch.
  {0} home             * Open the folder containing the build.yaml.
  {0} modules          * Open the folder containing the course modules.
  {0} repo             * Open the root of the training repo in git.
  {0} yaml               Edit the build.yaml.
  {0} config             Edit your course script configuration file.
  {0} showconfig         Print the in-memory configuration, which is
  {1}                    the parsed configuration file and possible
  {1}                    environment overrides.
  {0} guide            * Edit the instructor guide.               
  {0} deploy-images      Deploy the course images to S3. NOTE: This
  {1}                    command is a stub. It will be implemented in 
  {1}                    a later release.
  {0} set VAR=VALUE      Configure and save a setting. Note that the 
  {1}                    keys are not validated. Spelling matters!
  {0} grep [-i] <re>     Search for a regular expression in course 
  {1}                    notebooks. The grep is done internally (in
  {1}                    Python), so any regular expression accepted
  {1}                    by Python is suitable. Use "-i" to specify
  {1}                    case-blind matching.
  {0} sed <command>      Search/replace text in notebooks using 
  {1}                    "sed -i -E". Takes a single "sed" argument
  {1}                    and requires a version of "sed" that supports
  {1}                    the "-i" (inplace edit) option. (The stock
  {1}                    ("sed" on the Mac and on Linux both qualify.)

  The following subcommands consume all remaining arguments and end the chain.

  {0} xargs <command>    Run <command> once per notebook.

  The following settings are honored. They are first read from the environment.
  If not there, {0} looks for them in the configuration file, located at
  "{CONFIG_PATH}".
  
  DB_CONFIG_PATH: Path to .databrickscfg
    Default: {DB_CONFIG_PATH_DEFAULT}
  DB_PROFILE: Profile to use within .databrickscfg profile
    Default: {DB_PROFILE_DEFAULT}
  DB_SHARD_HOME: Workspace path for home folder in Databricks. Required.
  COURSE_DEBUG: Set to 'true' (in environment) to enable debug messages.
    Default: false
  COURSE_NAME: Name of the course you wish to work on.
    Default: This must be provided, but can default from the stored config.
  COURSE_REPO: Path to git repo
    Default: {COURSE_REPO_DEFAULT}
  COURSE_HOME: Path to course in git repo
    Default: <COURSE_REPO>/courses/<course-name>
  COURSE_YAML: Path to the build.yaml
    Default: <COURSE_HOME>/build.yaml
  COURSE_MODULES: Path to modules in git repo
    Default: <COURSE_REPO>/modules/<course-name>
  COURSE_REMOTE_SOURCE: Workspace path for course source
    Default: <DB_SHARD_HOME>/<SOURCE>/<course-name>
  COURSE_REMOTE_TARGET: Workspace path for built course
    Default: <DB_SHARD_HOME>/<TARGET>/<course-name>
  COURSE_AWS_PROFILE: AWS authentication profile to use when uploading to S3. 
    Default: {AWS_PROFILE_DEFAULT}
  SELF_PACED_PATH: A Unix-style path of directories to search for self-paced
                   classes. Each directory is relative to <COURSE_REPO>.
                   "course" searches each of these directories for 
                   subdirectories that contain "build.yaml" files, and it
                   assumes each of those subdirectories is a self-paced course.
    Default: {SELF_PACED_PATH_DEFAULT}
  SOURCE: Prefix for uploading/downloading source files.
    Default: {SOURCE_DEFAULT}
  TARGET: Prefix for uploading/downloading built files.
    Default: {TARGET_DEFAULT}
  EDITOR: Text editor program
    Default: {EDITOR_DEFAULT}
  PAGER: Program to scroll text output
    Default: {PAGER_DEFAULT}
  OPEN_DIR: Program to use to open a folder
    Default: {OPEN_DIR_DEFAULT}
'''.format(
    PROG,
    ' ' * len(PROG),
    CONFIG_PATH=CONFIG_PATH,
    VERSION=VERSION,
    PAGER_DEFAULT=PAGER_DEFAULT,
    DB_CONFIG_PATH_DEFAULT=DB_CONFIG_PATH_DEFAULT,
    DB_PROFILE_DEFAULT=DB_PROFILE_DEFAULT,
    COURSE_REPO_DEFAULT=COURSE_REPO_DEFAULT,
    AWS_PROFILE_DEFAULT=AWS_PROFILE_DEFAULT,
    SOURCE_DEFAULT=SOURCE_DEFAULT,
    TARGET_DEFAULT=TARGET_DEFAULT,
    EDITOR_DEFAULT=EDITOR_DEFAULT,
    OPEN_DIR_DEFAULT=OPEN_DIR_DEFAULT,
    SELF_PACED_PATH_DEFAULT=SELF_PACED_PATH_DEFAULT
)

WARNING_PREFIX = 'WARNING: '
ERROR_PREFIX = 'ERROR: '
DEBUG_PREFIX = '(DEBUG) '
COLUMNS = int(os.environ.get('COLUMNS', '80')) - 1

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class CourseError(Exception):
    pass

# -----------------------------------------------------------------------------
# Internal functions
# -----------------------------------------------------------------------------

@contextmanager
def noop(result: Any, *args: Any, **kw: Any) -> Any:
    """
    A no-op context manager, with is occasionally useful. Yields its first
    positional parameter. Ignores all the others.

    :param result: what to yield
    :param args:   remaining positional parameters (ignored)
    :param kw:     keyword parameters. Ignored.
    """
    yield result


@contextmanager
def pager(cfg: Dict[str, str]) -> Generator[None, TextIO, None]:
    """
    Provides a convenient way to write output to a pager. This context
    manager yields a file descriptor you can use to write to the pager.
    If the pager isn't defined, the file descriptor will just be stdout.
    This function manages cleanup and ensures that the pager has proper
    access to the terminal.

    :param cfg: the loaded configuration

    :returns: the file descriptior (as a yield)
    """
    # Dump to a temporary file if the pager is defined. This allows the pager
    # to use stdin to read from the terminal.
    the_pager = cfg.get('PAGER')
    if the_pager:
        opener = NamedTemporaryFile
    else:
        # If this confuses you, go here:
        # https://docs.python.org/2/library/functools.html#functools.partial
        opener = functools.partial(noop, sys.stdout)

    with opener(mode='w') as out:
        yield out
        out.flush()

        if the_pager:
            # In this case, we know we have a NamedTemporaryFile. We can
            # send the temporary file to the pager.
            p = Popen(f'{the_pager} <{out.name}', shell=True)
            p.wait()


def check_for_docker(command: str) -> NoReturn:
    # Note: This path is created by the shell script (../docker/create-image.sh)
    # specifically so we can test for it.
    if os.path.exists("/etc/in-docker"):
        raise CourseError(
            f'"{PROG} {command}" does not work inside a Docker container.'
        )


def cmd(shell_command: str,
        quiet: bool = False,
        dryrun: bool = False) -> NoReturn:
    """
    Run a shell command.

    :param shell_command: the string containing the command and args
    :param quiet:         True: don't echo the command before running it.
    :param dryrun:        echo the command, but don't run it
    :raises CourseError: If the command exits with a non-zero status
    """
    if dryrun or (not quiet):
        print(f"+ {shell_command}")

    if not dryrun:
        rc = os.system(shell_command)
        if rc != 0:
            raise CourseError(f'Command exited with {rc}')


def quote_shell_arg(arg: str) -> str:
    """
    Ensure that an argument to be passed to a shell command is quoted.

    :param arg:
    :return: possibly changed argument
    """
    quoted = ''
    q = arg[0]
    if q in ('"', "'"):
        # Already quoted, hopefully.
        if arg[-1] != q:
            raise CourseError(f'Mismatched quotes in shell argument: {arg}')
        quoted = arg
    elif ('"' in arg) and ("'" in arg):
        raise CourseError(
            'Shell argument cannot be quoted, since it contains single AND '
            f'double quotes: {arg}'
        )
    elif "'" in arg:
        quoted = '"' + arg + '"'
    else:
        quoted = "'" + arg + "'"

    return quoted


def load_config(config_path: str,
                apply_defaults: bool = True,
                show_warnings: bool = False) -> Dict[str, str]:
    """
    Load the configuration file.

    :param config_path:    path to the configuration file
    :param apply_defaults: If True (default), apply all known default values.
                           If False, just return what's in the config file.
    :param show_warnings:  Warn about some things. Generally only desirable
                           at program startup.

    :return: A dictionary of configuration items
    """
    bad = False
    comment = re.compile("^\s*#.*$")
    cfg = {}
    parent_dir = os.path.dirname(config_path)
    if os.path.isfile(parent_dir):
        raise CourseError(
            f'''"{parent_dir}" already exists, but it isn't a directory.'''
        )
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    if os.path.exists(config_path):
        with open(config_path) as f:
            for (i, line) in enumerate([l.rstrip() for l in f.readlines()]):
                lno = i + 1
                if len(line.strip()) == 0:
                    continue
                if comment.search(line):
                    continue
                fields = line.split('=')
                if len(fields) != 2:
                    bad = True
                    error(f'"{config_path}", line {lno}: Malformed line')
                    continue

                cfg[fields[0]] = fields[1]

        if bad:
            raise CourseError("Configuration error(s).")

    setting_keys_and_defaults = (
        # The second item in each tuple is a default value. The third item
        # indicates whether it can be overridden in the configuration or
        # the environment.
        #
        # The default is treated as a Python string template, so it can
        # substitute values from previous entries in the list. If the default
        # value is None, that generally means it can be overridden on the
        # command line (or depends on something else that can be), so it's
        # checked at runtime.
        ('DB_CONFIG_PATH', DB_CONFIG_PATH_DEFAULT, True),
        ('DB_PROFILE', DB_PROFILE_DEFAULT, True),
        ('DB_SHARD_HOME', None, True),
        ('PREFIX', None, True),                      # set later
        ('COURSE_NAME', None, True),                 # can be overridden
        ('COURSE_REPO', COURSE_REPO_DEFAULT, True),
        ('COURSE_HOME', None, False),                # depends on COURSE_NAME
        ('COURSE_YAML', None, True),
        ('COURSE_MODULES', None, False),             # depends on COURSE_NAME
        ('COURSE_REMOTE_SOURCE', None, False),       # depends on COURSE_NAME
        ('COURSE_REMOTE_TARGET', None, False),       # depends on COURSE_NAME
        ('COURSE_AWS_PROFILE',  AWS_PROFILE_DEFAULT, True),
        ('SELF_PACED_PATH', SELF_PACED_PATH_DEFAULT, True),
        ('SOURCE', SOURCE_DEFAULT, True),
        ('TARGET', TARGET_DEFAULT, True),
        ('EDITOR', EDITOR_DEFAULT, True),
        ('PAGER', PAGER_DEFAULT, True),
        ('OPEN_DIR', OPEN_DIR_DEFAULT, True),
    )

    # Remove anything that cannot be overridden.

    for e, default, allow_override in setting_keys_and_defaults:
        if (default is not None):
            continue

        v = cfg.get(e)
        if not v:
            continue

        if not allow_override:
            if show_warnings:
                warn(f'Ignoring "{e}" in the configuration file, because ' +
                     "it's calculated at run-time.")
            del cfg[e]

    if apply_defaults:
        # Apply environment overrides. Then, check for missing ones where
        # appropriate, and apply defaults.
        for e, default, _ in setting_keys_and_defaults:
            v = os.environ.get(e)
            if v is not None and ("FORCE_" + e) not in cfg:
                cfg[e] = v

            if not cfg.get(e) and default:
                t = StringTemplate(default)
                cfg[e] = t.substitute(cfg)

    return cfg


def get_self_paced_courses(cfg: Dict[str, str]) -> Sequence[str]:
    """
    Find the names of all self-paced courses by querying the local Git repo
    clone.

    :param cfg  the loaded config. COURSE_REPO and SELF_PACED_PATH must be
                set

    :return: the names of all self-paced courses (as simple directory names)
    """

    self_paced_path = cfg['SELF_PACED_PATH']

    for rel_path in self_paced_path.split(':'):
        self_paced_dir = os.path.join(cfg['COURSE_REPO'], rel_path)
        if not os.path.isdir(self_paced_dir):
            debug(f'Directory "{self_paced_dir}" (in SELF_PACED_PATH) ' +
                  'does not exist.')
            continue

        for f in os.listdir(self_paced_dir):
            if f[0] == '.':
                continue
            full_path = os.path.join(self_paced_dir, f)

            if not os.path.isdir(full_path):
                continue
            for course_file in os.listdir(full_path):
                p = os.path.join(full_path, course_file)
                if os.path.isdir(p):
                    continue
                _, ext = os.path.splitext(course_file)
                if course_file.startswith("build") and ext == '.yaml':
                    yield f
                    break


def update_config(cfg: Dict[str, str]) -> Dict[str, str]:
    """
    Update the configuration, setting values that depend on course name,
    which is assumed to be set in the configuration.

    :param cfg: current configuration

    :return: possibly adjusted configuration
    :raises CourseError: Configuration error.
    """
    course = cfg.get('COURSE_NAME')
    if not course:
        return cfg

    from os.path import join, normpath

    adj = cfg.copy()
    repo = adj['COURSE_REPO']

    self_paced = list(get_self_paced_courses(cfg))
    prefix = 'Self-Paced' if course in self_paced else ''

    adj['PREFIX'] = prefix
    adj['COURSE_HOME'] = normpath(join(repo, 'courses', prefix, course))
    if not adj.get('COURSE_YAML'):
        adj['COURSE_YAML'] = join(adj['COURSE_HOME'], 'build.yaml')
    adj['COURSE_MODULES'] = join(repo, 'modules', prefix, course)

    db_shard_home = adj.get('DB_SHARD_HOME')
    if not db_shard_home:
        # Let the databricks Workspace layer figure out the appropriate value
        # for home.
        try:
            w = databricks.Workspace(adj['DB_PROFILE'])
            db_shard_home = w.home
        except databricks.DatabricksError as e:
            # Ignore config errors. ~/.databrickscfg might not be there.
            if e.code != databricks.StatusCode.CONFIG_ERROR:
                raise

    if db_shard_home:
        adj['COURSE_REMOTE_SOURCE'] = f'{db_shard_home}/{adj["SOURCE"]}/{course}'
        adj['COURSE_REMOTE_TARGET'] = f'{db_shard_home}/{adj["TARGET"]}/{course}'

    return adj


def check_config(cfg: Dict[str, str], *keys: str) -> NoReturn:
    """
    Check the configuration, aborting if required items (COURSE_NAME and
    COURSE_REPO) are missing. Only useful for commands that actually do work.

    :param cfg:  the configuration
    :param keys: the keys to require. If not specified, defaults to the
                 ones listed above.

    :return: None

    :raises ConfigError: on error
    """
    if not keys:
        keys = ('COURSE_NAME', 'COURSE_REPO')
    for key in keys:
        if not cfg.get(key):
            raise CourseError(
                f'{key} must be set, either in the environment or in the ' +
                'configuration file.'
            )


def build_file_path(cfg: Dict[str, str]) -> NoReturn:
    """
    Return the path to the build file for the current course.

    :param cfg: the configuration. At a minimum, "COURSE_HOME" must be set.
                COURSE_YAML is also examined.

    :return: the path to the build file
    """
    res = cfg.get('COURSE_YAML')
    if res:
        if not os.path.sep in res:
            # Simple file name. Join it with the course home.
            res = os.path.join(cfg['COURSE_HOME'], res)
    else:
        res = os.path.join(cfg['COURSE_HOME'], 'build.yaml')

    return res


def configure(cfg: Dict[str, str],
              config_path: str,
              key: str,
              value: str) -> Dict[str, str]:
    """
    Add or update a key=value setting in both the in-memory configuration and
    the stored configuration.

    :param cfg:         the in-memory config
    :param config_path: the path to the stored configuration
    :param key:         the key to add or update
    :param value:       the new value

    :return: the adjusted in-memory configuration, which is a copy of the
             one passed in
    """
    new_cfg = cfg.copy()
    new_cfg[key] = value
    # Don't update from the in-memory config, because it might not match
    # what's in the file. (It can be modified on the fly, based on the command
    # line, and those ephemeral changes should not be saved.)
    stored_cfg = load_config(config_path, apply_defaults=False)
    stored_cfg[key] = value
    with open(config_path, 'w') as f:
        for k, v in sorted(stored_cfg.items()):
            f.write(f'{k}={v}\n')

    return new_cfg


def work_on(cfg: Dict[str, str],
            course_name: str,
            config_path: str) -> Dict[str, str]:
    """
    Change the course name in the configuration. Implicitly updates the
    in-memory configuration by calling update_config().

    :param cfg:
    :param course_name:
    :param config_path:
    :return:
    """
    return update_config(
        configure(cfg, config_path, 'COURSE_NAME', course_name)
    )


def clean(cfg: Dict[str, str]) -> NoReturn:
    """
    The guts of the "clean" command, this function deletes the built (target)
    notebooks for current course from the remote Databricks instance.

    :param cfg: The config. COURSE_NAME, COURSE_REMOTE_TARGET, and DB_PROFILE
                are assumed to be set.

    :return: Nothing
    """
    check_config(cfg)
    db_profile = cfg['DB_PROFILE']
    remote_target = cfg['COURSE_REMOTE_TARGET']

    # It's odd to ensure that the directory exists before removing it, but
    # it's easier (and costs no more time, really) than to issue a REST call
    # to check whether it exists in the first place. And "rm" will die if
    # called on a nonexistent remote path.
    w = databricks.Workspace(profile=db_profile)
    w.mkdirs(remote_target)
    w.rm(remote_target, recursive=True)


def clean_source(cfg: Dict[str, str]) -> NoReturn:
    """
    The guts of the "clean-source" command, this function deletes the source
    notebooks for current course from the remote Databricks instance.

    :param cfg: The config. COURSE_NAME, COURSE_REMOTE_SOURCE, and DB_PROFILE
                are assumed to be set.

    :return: Nothing
    """
    check_config(cfg)
    db_profile = cfg['DB_PROFILE']
    remote_source = cfg['COURSE_REMOTE_SOURCE']

    w = databricks.Workspace(profile=db_profile)
    w.mkdirs(remote_source)
    w.rm(remote_source, recursive=True)


def download(cfg: Dict[str, str]) -> NoReturn:
    """
    Download the source notebooks for the current course from the Databricks
    instance and put them back into the local Git repository. Delegates the
    actual download to bdc.

    :param cfg: The config. COURSE_HOME (and, by implication, COURSE_NAME) and
                DB_PROFILE are assumed to be set.

    :return: Nothing
    """
    check_config(cfg)
    db_profile = cfg['DB_PROFILE']
    bdc.bdc_download(build_file=build_file_path(cfg),
                     shard_path=cfg['COURSE_REMOTE_SOURCE'],
                     databricks_profile=db_profile,
                     verbose=False)


def upload(cfg: Dict[str, str]) -> NoReturn:
    """
    Upload the source notebooks for the current course from the local Git
    repository to the Databricks instance. Delegates the actual upload to bdc.

    :param cfg: The config. COURSE_HOME (and, by implication, COURSE_NAME),
                COURSE_REMOTE_SOURCE, and DB_PROFILE are assumed to be set.

    :return: Nothing
    """
    check_config(cfg)
    db_profile = cfg['DB_PROFILE']
    bdc.bdc_upload(build_file=build_file_path(cfg),
                   shard_path=cfg['COURSE_REMOTE_SOURCE'],
                   databricks_profile=db_profile,
                   verbose=False)


def import_dbcs(cfg:        Dict[str, str],
                build_dir:  str,
                build_file: str) -> NoReturn:
    """
    Find all DBC files under the build output directory for the current course,
    and upload them (import them) into the Databricks instance.

    :param cfg:       The config. COURSE_NAME, COURSE_REMOTE_TARGET, and
                      DB_PROFILE are assumed to be set.
    :param build_dir: The path to the build directory.

    :return: NOthing
    """
    check_config(cfg)
    remote_target = cfg['COURSE_REMOTE_TARGET']
    db_profile = cfg['DB_PROFILE']

    def import_dbc(dbc: str, build: bdc.BuildData) -> NoReturn:
        '''
        Import a single DBC.

        Assumes (a) the working directory is the build directory, and
        (b) that the remote target path has already been created.
        '''
        w = databricks.Workspace(profile=db_profile)
        if build.has_profiles:
            parent_subpath = os.path.dirname(dbc)
            dir_to_make = f'{remote_target}/{os.path.dirname(parent_subpath)}'
            w.mkdirs(dir_to_make)
            remote_path = f'{remote_target}/{parent_subpath}'
        else:
            remote_path = remote_target

        info(f'Importing "{dbc}" to "{remote_path}"...')
        w.import_dbc(dbc, remote_path)

    # Get the build information. We'll need it later.
    build = bdc.bdc_load_build(build_file)

    print(f'Importing all DBCs under "{build_dir}" to remote "{remote_target}"')
    dbcs = []
    with working_directory(build_dir) as pwd:
        for dirpath, _, filenames in os.walk('.'):
            for filename in filenames:
                _, ext = os.path.splitext(filename)
                if ext != '.dbc':
                    continue
                dbcs.append(os.path.normpath(os.path.join(dirpath, filename)))

        if not dbcs:
            warn('No DBCs found.')
        else:
            clean(cfg)
            w = databricks.Workspace(profile=db_profile)
            # If we're doing a profile-based build, create the remote target.
            # The import operations will implicitly create the remote
            # subfolders. However, if we're not doing profile-based builds,
            # then creating the remote target ahead of time will cause the
            # import to fail, so don't do that.
            if build.has_profiles:
                w.mkdirs(remote_target)

            for dbc in dbcs:
                info(f'\nIn "{pwd}":')
                import_dbc(dbc, build)


def build_local(cfg: Dict[str, str]) -> str:
    """
    Build a course without uploading the results.

    :param cfg: the loaded config

    :return: the path to the build file, for convenience
    """
    check_config(cfg, 'COURSE_NAME', 'COURSE_REPO')
    course_name = cfg['COURSE_NAME']
    build_file = build_file_path(cfg)
    if not os.path.exists(build_file):
        die('Build file "{}" does not exist.'.format(build_file))

    print(f"\nBuilding {course_name} using {os.path.basename(build_file)}")
    bdc.bdc_build_course(build_file,
                         dest_dir='',
                         overwrite=True,
                         verbose=False)

    return build_file


def build_and_upload(cfg: Dict[str, str]) -> NoReturn:
    """
    Build the current course and upload (import) the built artifacts to the
    Databricks instance.

    :param cfg:  The config. COURSE_NAME, COURSE_REMOTE_TARGET, and
                 DB_PROFILE are assumed to be set.

    :return: Nothing
    """
    check_config(cfg)
    build_file = build_local(cfg)
    build_dir = bdc.bdc_output_directory_for_build(build_file)
    import_dbcs(cfg, build_dir, build_file)


def upload_build(cfg: Dict[str, str]) -> NoReturn:
    """
    Upload an already-built course.

    :param cfg: The config. COURSE_NAME, COURSE_REMOTE_TARGET, and
                DB_PROFILE are assumed to be set.

    :return: None
    """
    check_config(cfg)
    build_file = build_file_path(cfg)
    build_dir = bdc.bdc_output_directory_for_build(build_file)
    import_dbcs(cfg, build_dir)


def install_tools() -> NoReturn:
    """
    Install the build tools. Doesn't work inside a Docker container.
    """
    info('"course install-tools" is deprecated, because it is not possible '
         'to update a Docker container from within itself. To update the '
         'build tools, run the following command:\n\n'
         'curl -L https://git.io/fhaLg | bash')


def browse_directory(cfg: Dict[str, str],
                     path: str,
                     subcommand: str) -> NoReturn:
    """
    Browse a directory, using whatever tool is configured as OPEN_DIR.
    Does not work inside Docker.

    :param cfg:         the loaded configuration
    :param path:        the path to the directory
    :param subcommand:  the "course" subcommand, for errors.

    :return: Nothing.
    """
    check_for_docker(subcommand)
    open_dir = cfg['OPEN_DIR']
    cmd(f'{open_dir} "{path}"')


def edit_file(cfg: Dict[str, str], path: str, subcommand: str) -> NoReturn:
    """
    Edit a file, using the configured EDITOR. Works inside Docker, provided
    EDITOR is set to something installed in the Docker instance (such as
    "vim").

    :param cfg:         the loaded configuration
    :param path:        the path to the file
    :param subcommand:  the "course" subcommand, for errors.

    :return: Nothing
    """
    check_config(cfg, 'COURSE_NAME', 'COURSE_REPO')
    editor = cfg['EDITOR']
    cmd(f'{editor} "{path}"')


def edit_config(cfg: Dict[str, str]) -> Dict[str, str]:
    """
    Edit the "course" configuration file, using the configured EDITOR. Works
    inside Docker, provided EDITOR is set to something installed in the Docker
    instance (such as "vim").

    Automatically reloads the configuration after the edit.

    :param cfg: the loaded configuration

    :return: The possibly modified configuration
    """
    edit_file(cfg, CONFIG_PATH, 'config')
    return load_config(CONFIG_PATH, show_warnings=True)


def git_status(cfg: Dict[str, str]) -> NoReturn:
    """
    Runs a "git status" against the local Git repository.

    :param cfg: the loaded config. COURSE_REPO must be set.

    :return: Nothing
    """
    course_repo = cfg['COURSE_REPO']
    print(f'+ cd {course_repo}')
    with working_directory(course_repo):
        cmd("git status")


def git_diff(cfg: Dict[str, str]) -> NoReturn:
    """
    Runs a "git diff" against the local Git repository.

    :param cfg: the loaded config. COURSE_REPO must be set. PAGER will be
                used if it is set.

    :return: Nothing
    """
    check_config(cfg, 'COURSE_REPO')
    course_repo = cfg['COURSE_REPO']
    pager = cfg['PAGER']
    with working_directory(course_repo):
        if not pager:
            cmd("git diff")
        else:
            cmd(f"git diff | {pager}")


def git_difftool(cfg: Dict[str, str]) -> NoReturn:
    """
    Runs a "git difftool", using "opendiff", against the local Git repository.
    Does not work inside a Docker container.

    :param cfg: the loaded config. COURSE_REPO must be set.

    :return: Nothing
    """
    check_config(cfg, 'COURSE_REPO')
    course_repo = cfg['COURSE_REPO']
    check_for_docker("difftool")
    with working_directory(course_repo):
        cmd("git difftool --tool=opendiff --no-prompt")


def git_tag(cfg: Dict[str, str]) -> NoReturn:
    """
    Tag the git repo and branch with the course name and version.

    :param cfg: the loaded config. COURSE_YAML must be set.

    :return: Nothing.
    """
    build_file = build_file_path(cfg)
    bdc.bdc_create_git_tag(build_file)


def deploy_images(cfg: Dict[str, str]) -> NoReturn:
    """
    Deploy the images for a course to the appropriate S3 location.

    STUB. NOT CURRENTLY IMPLEMENTED.

    :param cfg: the loaded configuration

    :return: Nothing
    """
    warn("'deploy-images' is not yet implemented.")


def grep(cfg: Dict[str, str],
         pattern: str,
         case_blind: bool = False) -> NoReturn:
    """
    Searches for the specified regular expression in every notebook within
    the current course, printing the colorized matches to standard output.
    If PAGER is set, the matches will be piped through the pager.

    Note that this function does NOT use grep(1). It implements the
    regular expression matching and colorization entirely within Python.

    :param cfg:          The config.
    :param pattern:      The regular expression (a string, not a compiled
                         pattern) to find
    :param case_blind:   Whether or not to use case-blind matching

    :return: Nothing
    """

    def grep_one(path: str, r: Pattern, out: TextIO) -> NoReturn:
        home = os.environ['HOME']
        if home:
            printable_path = os.path.join(
                '~', path[len(home)+1:]
            )
        else:
            printable_path = path

        matches = []
        with open(path) as f:
            for line in f.readlines():
                m = r.search(line)
                if not m:
                    continue

                # If there's a pager, colorize the match.
                if cfg.get('PAGER'):
                    s = m.start()
                    e = m.end()
                    matches.append(
                        line[:s] +
                        colored(line[s:e], 'red', attrs=['bold']) +
                        line[e:])
                else:
                    matches.append(line)

        if matches:
            out.write(f'\n\n=== {printable_path}\n\n')
            out.write(''.join(matches))

    r = None
    try:
        flags = 0 if not case_blind else re.IGNORECASE
        r = re.compile(pattern, flags=flags)
    except Exception as e:
        die(f'Cannot compile regular expression "{pattern}": {e}')

    check_config(cfg, 'COURSE_NAME', 'COURSE_REPO')
    with pager(cfg) as out:
        for nb in bdc.bdc_get_notebook_paths(build_file_path(cfg)):
            grep_one(nb, r, out)


def sed(cfg: Dict[str, str], sed_cmd: str) -> NoReturn:
    """
    Runs an in-place "sed" edit against every notebook in the course, using
    "sed -E". Requires a version of "sed" that supports the "-i" (in-place
    edit) option.

    :param cfg:     the loaded configuration
    :param sed_cmd: the "sed" command, which may or may not be quoted.

    :return: Nothing
    """
    check_config(cfg, 'COURSE_NAME', 'COURSE_REPO')
    for nb in bdc.bdc_get_notebook_paths(build_file_path(cfg)):
        # Quote the argument.
        q = sed_cmd[0]
        if q in ('"', "'"):
            # Already quoted, hopefully.
            if sed_cmd[-1] != q:
                raise CourseError(
                    f'Mismatched quotes in sed argument: {sed_cmd}'
                )
            quoted = sed_cmd
        elif ('"' in sed_cmd) and ("'" in sed_cmd):
            raise CourseError(
                '"sed" argument cannot be quoted, since it contains ' +
                f'single AND double quotes: {sed_cmd}'
             )
        elif "'" in sed_cmd:
            quoted = '"' + sed_cmd + '"'
        else:
            quoted = "'" + sed_cmd + "'"

        cmd(f'sed -E -i "" -e {quoted} "{nb}"')


def run_command_on_notebooks(cfg: Dict[str, str],
                             command: str,
                             args: Sequence[str]) -> NoReturn:
    """
    Runs a command on every notebook in the current course.

    :param cfg:      the loaded configuration.
    :param command:  the command to run
    :param args:     any command arguments, as a list

    :return: Nothing
    """
    check_config(cfg, 'COURSE_NAME', 'COURSE_REPO')
    for nb in bdc.bdc_get_notebook_paths(build_file_path(cfg)):
        if args:
            quoted = ' '.join([quote_shell_arg(arg) for arg in args])
            shell_command = f'{command} {quoted} {nb}'
        else:
            shell_command = f'{command} {nb}'

        try:
            cmd(shell_command)
        except CourseError as e:
            warn(str(e))


def help(cfg: Dict[str, str]) -> NoReturn:
    with pager(cfg) as out:
        out.write(USAGE)


def print_tool_versions() -> NoReturn:
    import gendbc
    import master_parse
    import db_edu_util
    from databricks_cli.version import version as dbcli_version




    print(f"course:                {VERSION}")
    print(f"bdc:                   {bdc.VERSION}")
    print(f"gendbc:                {gendbc.VERSION}")
    print(f"master_parse:          {master_parse.VERSION}")
    print(f"db_edu_util (library): {db_edu_util.VERSION}")
    print(f"databricks:            {dbcli_version}")


def which(cfg: Dict[str, str]) -> NoReturn:
    course_name = cfg.get('COURSE_NAME')
    if course_name:
        print(cfg['COURSE_NAME'])
    else:
        print('No course has been set.')


# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------

def main():
    if os.environ.get('COURSE_DEBUG', 'false') == 'true':
        set_debug(True)

    try:
        # Load the configuration and then run it through update_config() to
        # ensure that course name-related settings are updated, if necessary.
        cfg = update_config(load_config(CONFIG_PATH, show_warnings=True))

        # Update the environment, for subprocesses we need to invoke.

        os.environ['EDITOR'] = cfg['EDITOR']
        os.environ['PAGER'] = cfg['PAGER']

        # Loop over the argument list, since we need to support chaining some
        # commands (e.g., "course download build"). This logic emulates
        # what was in the original shell script version, and it's not easily
        # handled by Python's argparse or docopt. So, ugly as it is, we go
        # with manual parsing.

        if len(sys.argv) == 1:
            args = ["help"]
        else:
            args = sys.argv[1:]

        i = 0
        while i < len(args):
            cmd = args[i]

            if cmd in ('--version', '-V'):
                print(VERSION)
                break

            if cmd in ('toolversions', 'tool-versions'):
                print_tool_versions()
                break

            if cmd in ('-n', '--name'):
                try:
                    i += 1
                    # Changing the name of the course has to reset the
                    # build.yaml name.
                    del cfg['COURSE_YAML']
                    cfg['COURSE_NAME'] = args[i]
                    cfg = update_config(cfg)
                except IndexError:
                    die("Saw -n or --name without subsequent course name.")

            elif cmd in ('-f', '--build-file'):
                try:
                    i += 1
                    cfg['COURSE_YAML'] = args[i]
                    cfg = update_config(cfg)
                except IndexError:
                    die("Saw -f or --build-file without subsequent file name.")

            elif cmd in ('-h', '--help', 'help', 'usage'):
                help(cfg)
                break

            elif cmd in ('work-on', 'workon'):
                try:
                    i += 1
                    cfg = work_on(cfg, args[i], CONFIG_PATH)
                except IndexError:
                    die('Expected course name after "work-on".')

            elif cmd == 'tag':
                git_tag(cfg)

            elif cmd == 'which':
                which(cfg)

            elif cmd in ('install-tools', 'installtools'):
                install_tools()

            elif cmd == 'download':
                download(cfg)

            elif cmd == 'upload':
                upload(cfg)

            elif cmd in ('upload-built', 'uploadbuilt'):
                upload_build(cfg)

            elif cmd == 'build':
                build_and_upload(cfg)

            elif cmd in ('build-local', 'buildlocal'):
                build_local(cfg)

            elif cmd == 'clean':
                clean(cfg)

            elif cmd in ('clean-source', 'cleansource'):
                clean_source(cfg)

            elif cmd in ('deploy-images', 'deployimages'):
                deploy_images(cfg)

            elif cmd == 'status':
                git_status(cfg)

            elif cmd == 'diff':
                git_diff(cfg)

            elif cmd == 'difftool':
                git_difftool(cfg)

            elif cmd == 'home':
                browse_directory(cfg, cfg['COURSE_HOME'], 'home')

            elif cmd == 'modules':
                browse_directory(cfg, cfg['COURSE_MODULES'], 'modules')

            elif cmd == 'repo':
                browse_directory(cfg, cfg['COURSE_REPO'], 'repo')

            elif cmd == 'config':
                cfg = edit_config(cfg)

            elif cmd == 'yaml':
                edit_file(cfg, build_file_path(cfg), 'yaml')

            elif cmd == 'guide':
                edit_file(cfg,
                          os.path.join(cfg['COURSE_HOME'], 'Teaching-Guide.md'),
                          'guide')

            elif cmd == ('deploy-images', 'deployimages'):
                deploy_images(cfg)

            elif cmd == 'grep':
                try:
                    i += 1
                    pattern = args[i]
                    if pattern == '-i':
                        case_blind = True
                        i += 1
                        pattern = args[i]
                    else:
                        case_blind = False

                    grep(cfg, pattern, case_blind)
                except IndexError:
                    die('Missing grep argument(s).')

            elif cmd == 'sed':
                try:
                    i += 1
                    sed(cfg, args[i])
                except IndexError:
                    die('Missing sed argument.')

            elif cmd == 'xargs':
                # All the remaining arguments go to the command.
                try:
                    i += 1
                    command = args[i]
                    if i < len(args):
                        i += 1
                        command_args = args[i:]
                    else:
                        command_args = []

                    run_command_on_notebooks(cfg, command, command_args)
                    break
                except IndexError:
                    die('Missing command to run.')

            elif cmd == 'set':
                try:
                    i += 1
                    setting = args[i]
                    fields = setting.split('=')
                    if len(fields) != 2:
                        die('Argument to "set" must be of the form CONF=VAL.')
                    key, value = fields
                    value = value.replace('"', '')
                    cfg = configure(cfg, CONFIG_PATH, key, value)
                except IndexError:
                    die('Missing CONF=VAL argument to "set".')

            elif cmd == "showconfig":
                hdr = "Current configuration"
                print('-' * len(hdr))
                print(hdr)
                print('-' * len(hdr))
                for key in sorted(cfg.keys()):
                    print(f'{key}="{cfg[key]}"')

            else:
                die(f'"{cmd}" is not a valid "course" subcommand.')

            i += 1

    except CourseError as e:
        error(str(e))

    except bdc.BDCError as e:
        error(str(e))

    except KeyboardInterrupt:
        error('\n*** Interrupted.')

if __name__ == '__main__':
    main()
