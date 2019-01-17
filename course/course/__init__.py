#!/usr/bin/env python

import os
import sys
import bdc
import re
from contextlib import contextmanager
from typing import Generator, Sequence

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

VERSION = '2.0.0'
PROG = os.path.basename(sys.argv[0])

EDITOR = os.environ.get("EDITOR", "open -a textedit")
PAGER = os.environ.get("PAGER", "less --RAW-CONTROL-CHARS")

COURSE_REPO = os.environ.get(
    "COURSE_REPO",
    os.environ.get("REPO", os.path.expanduser("~/repos/training"))
)
DB_CONFIG_PATH = os.environ.get("DB_CONFIG_PATH",
                                os.path.expanduser("~/.databricks.cfg"))
DB_PROFILE = os.environ.get("DB_PROFILE", "DEFAULT")
DB_SHARD_HOME = os.environ.get("DB_SHARD_HOME",
                               "/Users/{}@databricks.com".format(os.getlogin()))

PREFIX = os.environ.get("PREFIX", "")
SOURCE = os.environ.get("SOURCE", "_Source")
TARGET = os.environ.get("TARGET", "_Target")

CONFIG_PATH = os.path.expanduser("~/.databricks/course.cfg")
USAGE = '''
{0}, version {VERSION}

Usage:
  {0} (-h | --help | help | usage)
  {0} <subcommand> ...
  
Description:
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
      
Subcommands:

  The various "course" commands are listed below. Those marked with "*"
  will NOT work in a Docker container.

  {0} --help             Show abbreviated usage
  {0} help               Show the full help page (this output)
  {0} install-tools    * Install the build tools.
  {0} work-on <name>     Specify and remember the course to build,
                         upload, etc.
  {0} which              Print the name of the currently selected course.
  {0} download           Download from SOURCE
  {0} build              Build from local files and upload build to TARGET
  {0} upload             Upload local sources (from your Git repo) to SOURCE
  {0} clean              Remove TARGET (built artifact) from Databricks             
  {0} clean-source       Remove SOURCE (built artifact) from Databricks
  {0} status             Run a "git status" on the local repository clone.
  {0} diff               Run a "git diff" on the local repository clone, and
                         pipe the output through the PAGER (usually "more" or
                         "less"). If PAGER isn't set, the diff output is just
                         dumped to standard output.
  {0} difftool         * Run "git difftool" (with "opendiff") on the local
                         repository clone. 
  {0} home             * Open the folder containing the build.yaml.
  {0} modules          * Open the folder containing the course modules.
  {0} repo             * Open the root of the training repo in git.
  {0} yaml             * Edit the build.yaml.
  {0} config           * Edit your course script configuration file.
  {0} guide            * Open the instructor guide.               
  {0} stage              Deploy a build to the S3 staging area.               
  {0} release            Deploy a build to the S3 release area.               
  {0} deploy-images      Deploy the course images to S3.
  {0} set VAR=VALUE      Configure and save a setting. Note that the keys are
                         not currently validated, so spelling matters.  

  The following subcommands consume all remaining arguments and end the chain.
  
  {0} grep <pattern>     Search for a regular expression in course notebooks.
  {0} sed <commands>     Search/replace text in notebooks using "sed -E"
  {0} xargs <command>    Run <command> once per notebook.

Environment variables used:
  DB_CONFIG_PATH: Path to .databrickscfg
    Default: ~/.databrickscfg
    Current: {DB_CONFIG_PATH}
  DB_PROFILE: Profile to use within .databrickscfg profile
    Default: "DEFAULT"
    Current: {DB_PROFILE}
  DB_SHARD_HOME: Workspace path for home folder
    Default: /Users/[Username]
    Current: {DB_SHARD_HOME}
  COURSE_NAME: Name of the course you wish to build.
    Default: This must be provided, but can default from the stored config.
  COURSE_REPO: Path to git repo
    Default: ~/repos/training
    Current: {COURSE_REPO}
  COURSE_HOME: Path to course in git repo
    Default: {COURSE_REPO}/courses/<course-name>
  COURSE_YAML: Path to the build.yaml
    Default: {COURSE_REPO}/courses/<course-name>/build.yaml
  COURSE_MODULES: Path to modules in git repo
    Default: {COURSE_REPO}/modules/<course-name>
  COURSE_REMOTE_SOURCE: Workspace path for course source
    Default: {DB_SHARD_HOME}/{SOURCE}/<course-name>
  COURSE_REMOTE_TARGET: Workspace path for built course
    Default: {DB_SHARD_HOME}/{TARGET}/<course-name>
  PREFIX: Path to append to course names in git, such as /self-paced
    Default: "", unless it's a self-paced course.
  SOURCE: Prefix for uploading/downloading source files.
    Default: _Source
    Current: {SOURCE}
  TARGET: Prefix for uploading/downloading built files.
    Default: _Target
    Current: {TARGET}
  EDITOR: Text editor program
    Default: open -a textedit
    Current: {EDITOR}
  PAGER: Program to scroll text output
    Default: less --RAW-CONTROL-CHARS
    Current: {PAGER}
'''.format(
    PROG,
    CONFIG_PATH=CONFIG_PATH,
    VERSION=VERSION,
    DB_CONFIG_PATH=DB_CONFIG_PATH,
    DB_PROFILE=DB_PROFILE,
    DB_SHARD_HOME=DB_SHARD_HOME,
    COURSE_REPO=COURSE_REPO,
    PREFIX=PREFIX,
    SOURCE=SOURCE,
    TARGET=TARGET,
    EDITOR=EDITOR,
    PAGER=PAGER
)

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class CourseError(Exception):
    pass

# -----------------------------------------------------------------------------
# Internal functions
# -----------------------------------------------------------------------------

def printerr(msg):
    sys.stderr.write("{}\n".format(msg))


def die(msg):
    printerr(msg)
    sys.exit(1)


@contextmanager
def working_directory(dir):
    # type: (str) -> Generator
    cur = os.getcwd()
    os.chdir(dir)
    try:
        yield
    finally:
        os.chdir(cur)


def check_for_docker(command):
    if os.environ.get("DOCKER", "") == "true":
        raise CourseError(
            '"{} {}" does not work inside a Docker container.'.format(
              PROG, command
            )
        )


def cmd(shell_command):
    print("+ {}".format(shell_command))
    rc = os.system(shell_command)
    if rc != 0:
        raise CourseError('"{}" exited with {}.'.format(shell_command, rc))


def parse_config(config_path):
    # type: (str) -> dict
    bad = False
    comment = re.compile("^\s*#.*$")
    cfg = {}
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
                    printerr('"{}", line {}: Malformed line'.format(
                        config_path, lno
                    ))
                    continue

                cfg[fields[0]] = fields[1]

        if bad:
            raise CourseError("Configuration error(s).")

    return cfg


def config_val(config, var, default=None):
    # type: (dict, str, str) -> str
    """
    :param config:
    :param var:
    :param default:
    :return:
    """
    # Try the environment first. Then, fall back to the configuration.
    # If that fails, use the default.
    return os.environ.get(var, config.get(var, default))


def get_self_paced_courses(course_repo):
    self_paced_dir = os.path.join(course_repo, "courses", "Self-Paced")
    for f in os.listdir(self_paced_dir):
        if f[0] == '.':
            continue
        full_path = os.path.join(self_paced_dir, f)
        if not os.path.isdir(full_path):
            continue
        build = os.path.join(full_path, "build.yaml")
        if not os.path.exists(build):
            continue
        yield f


def course_config(config, course_repo):
    # type: (dict, str) -> (str, str, str)
    for name in [os.environ.get('COURSE_NAME'),
                 config.get('COURSE_NAME')]:
        if name:
            prefix = os.environ.get("PREFIX")
            if not prefix:
                if name in get_self_paced_courses(course_repo):
                    prefix = "Self-Paced"
                else:
                    prefix = ""
            course_home = os.environ.get(
                "COURSE_HOME",
                os.path.join(course_repo, 'courses', prefix, name)
            )
            return (name, prefix, course_home)

    die("Course name not specified and not in the environment or config.")


def course_home(course_name):
    home = os.environ.get('COURSE_HOME')
    if not home:
        possible_paths = [
            os.path.join(COURSE_REPO, 'courses', course_name),
            os.path.join(COURSE_REPO, 'courses', 'self-paced', course_name)
        ]

        for p in possible_paths:
            if os.path.exists(p) and os.path.isdir(p):
                home = p
                break
    if not home:
        raise CourseError('Cannot determine home for course "{}"'.format(home))

    return home


def course_remote_source(course_name, cfg):
    return config_val(
        cfg,
        "COURSE_REMOTE_SOURCE",
        "{}/{}/{}".format(DB_SHARD_HOME, SOURCE, course_name)
    )


def course_remote_target(course_name, cfg):
    return config_val(
        cfg,
        "COURSE_REMOTE_TARGET",
        "{}/{}/{}".format(DB_SHARD_HOME, TARGET, course_name)

    )


def build_file_path(course_name):
    # type: (str) -> str
    return os.environ.get('COURSE_YAML', os.path.join(
        course_home(course_name), 'build.yaml'
    ))


def configure(cfg, key, value, config_path):
    # type: (dict, str, str, str) -> dict
    cfg[key] = value
    # Don't update from the in-memory config, because it might not match
    # what's in the file. (It can be modified on the fly, based on the command
    # line, and those ephemeral changes should not be saved.)
    stored_cfg = parse_config(config_path)
    stored_cfg[key] = value
    with open(config_path, 'w') as f:
        for k, v in stored_cfg.items():
            f.write('{}={}\n'.format(k, v))

    return cfg


def work_on(course_name, cfg, config_path):
    # type: (str, dict, str) -> dict
    return configure(cfg, 'COURSE_NAME', course_name, config_path)


def show_course_name(cfg):
    # type: (dict) -> None
    print(cfg['COURSE_NAME'])


def clean(cfg, course_repo, db_profile):
    # type: (dict, str, str) -> None
    (course_name, prefix, course_home) = course_config(cfg, course_repo)
    remote_target = course_remote_target(course_name, cfg)
    # It's odd to ensure that the directory exists before removing it, but
    # it's easier (and costs no more time, really) than to issue a REST call
    # to check whether it exists in the first place. And "rm" will die if
    # called on a nonexistent remote path.
    cmd('databricks --profile "{}" workspace mkdirs "{}"'.format(
        db_profile, remote_target
    ))
    cmd('databricks --profile "{}" workspace rm --recursive "{}"'.format(
        db_profile, remote_target
    ))


def clean_source(cfg, course_repo, db_profile):
    # type: (dict, str, str) -> None
    (course_name, prefix, course_home) = course_config(cfg, course_repo)
    remote_source = course_remote_source(course_name, cfg)
    cmd('databricks --profile "{}" workspace mkdirs "{}"'.format(
        db_profile, remote_source
    ))
    cmd('databricks --profile "{}" workspace rm --recursive "{}"'.format(
        db_profile, remote_source
    ))


def upload(cfg, course_repo, db_profile):
    # type: (dict, str, str) -> None
    (course_name, prefix, course_home) = course_config(cfg, course_repo)

    bdc.bdc_upload(build_file=build_file_path(course_name),
                   shard_path=course_remote_source(course_name, cfg),
                   databricks_profile=db_profile,
                   verbose=False)


def import_dbcs(cfg, course_name, build_dir, course_repo, db_profile):
    # type: (dict, str, str, str, str) -> None

    remote_target = course_remote_target(course_name, cfg)

    def import_dbc(dbc):
        # type: (str) -> None
        '''
        Import a single DBC.

        Assumes (a) the working directory is the build output directory, and
        (b) that the remote target path has already been created.

        :param dbc:
        :return:
        '''
        parent_subpath = os.path.dirname(dbc)
        # Language is ignored by databricks, but it's a required option. <sigh>
        cmd(
            ('databricks --profile {} workspace import --format DBC ' +
             '--language Python "{}" "{}/{}"').format(
                db_profile, dbc, remote_target, parent_subpath

            )
        )

    print('Importing all DBCs under "{}"'.format(build_dir))
    dbcs = []
    with working_directory(build_dir):
        for dirpath, _, filenames in os.walk('.'):
            for filename in filenames:
                _, ext = os.path.splitext(filename)
                if ext != '.dbc':
                    continue
                dbcs.append(os.path.normpath(os.path.join(dirpath, filename)))

        if not dbcs:
            print('WARNING: No DBCs found.')
        else:
            clean(cfg, course_repo, db_profile)
            cmd('databricks --profile {} workspace mkdirs {}'.format(
                db_profile, remote_target
            ))
            for dbc in dbcs:
                import_dbc(dbc)


def build(cfg, course_repo, db_profile):
    # type: (dict, str, str) -> None
    (course_name, prefix, course_home) = course_config(cfg, course_repo)
    build_file = os.path.join(course_home, "build.yaml")
    if not os.path.exists(build_file):
        die('Build file "{}" does not exist.'.format(build_file))
    print("\nBuilding {}".format(course_name))
    bdc.bdc_build_course(build_file,
                         dest_dir='',
                         overwrite=True,
                         verbose=False)
    build_dir = bdc.bdc_output_directory_for_build(build_file)
    import_dbcs(cfg, course_name, build_dir, course_repo, db_profile)


def install_tools():
    check_for_docker("install-tools")


def download(cfg, course_repo, db_profile):
    # type: (dict, str, str) -> None
    (course_name, prefix, course_home) = course_config(cfg, course_repo)
    bdc.bdc_download(build_file=build_file_path(course_name),
                     shard_path=course_remote_source(course_name, cfg),
                     databricks_profile=db_profile,
                     verbose=False)


def open_home(cfg):
    # type: (dict) -> None
    check_for_docker('home')


def open_modules(cfg):
    # type: (dict) -> None
    check_for_docker('modules')


def open_repo(cfg):
    # type: (dict) -> None
    check_for_docker('repo')


def edit_build_file(cfg):
    # type: (dict) -> None
    check_for_docker('yaml')


def edit_config(cfg):
    # type: (dict) -> None
    check_for_docker('config')


def edit_guide(cfg):
    # type: (dict) -> dict
    check_for_docker('guide')
    return cfg


def copy_to_staging(cfg):
    # type: (dict) -> None
    pass


def copy_to_release(cfg):
    # type: (dict) -> None
    pass


def git_status(cfg, course_repo):
    # type: (dict, str) -> None
    print('+ cd {}'.format(course_repo))
    with working_directory(course_repo):
        cmd("git status")


def git_diff(cfg, course_repo, pager):
    # type: (dict, str, str) -> None
    with working_directory(course_repo):
        if len(pager.strip()) == 0:
            cmd("git status")
        else:
            cmd("git status | {}".format(pager))


def git_difftool(cfg, course_repo):
    # type: (dict, str) -> None
    check_for_docker("difftool")
    with working_directory(course_repo):
        cmd("git difftool --tool=opendiff --no-prompt")


def deploy_images(cfg, course_repo):
    # type: (dict, str) -> None
    pass


def grep(cfg, args):
    # type: (dict, Sequence[str]) -> None
    pass


def sed(cfg, args):
    # type: (dict, Sequence[str]) -> None
    pass


def run_command_on_notebooks(cfg, args):
    # type: (dict, Sequence[str]) -> None
    pass


# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------

def main():
    try:
        # Update the environment, for subprocesses we need to invoke.

        os.environ['EDITOR'] = EDITOR
        os.environ['PAGER'] = PAGER

        cfg = parse_config(CONFIG_PATH)

        # Loop over the argument list, since we need to support chaining some
        # commands (e.g., "course download build"). This logic emulates
        # what was in the original shell script version, and it's not easily
        # handled by Python's argparse or docopt. So, ugly as it is, we go
        # with manual parsing.

        if len(sys.argv) == 1:
            args = "help"
        else:
            args = sys.argv[1:]

        i = 0
        while i < len(args):
            cmd = args[i]
            if cmd in ('-n', '--name'):
                try:
                    i += 1
                    cfg['COURSE_NAME'] = args[i]
                except IndexError:
                    die("Saw -n or --name without subsequent course name.")

            elif cmd in ('-h', '--help', 'help', 'usage'):
                print(USAGE)
                break

            elif cmd in ('work-on', 'workon'):
                try:
                    i += 1
                    work_on(args[i], cfg, CONFIG_PATH)
                except IndexError:
                    die('Expected course name after "work-on".')

            elif cmd == 'which':
                show_course_name(cfg)

            elif cmd == 'install_tools':
                install_tools()

            elif cmd == 'download':
                download(cfg, COURSE_REPO, DB_PROFILE)

            elif cmd == 'upload':
                upload(cfg, COURSE_REPO, DB_PROFILE)

            elif cmd == 'build':
                build(cfg, COURSE_REPO, DB_PROFILE)

            elif cmd == 'clean':
                clean(cfg, COURSE_REPO, DB_PROFILE)

            elif cmd in ('clean-source', 'cleansource'):
                clean_source(cfg, COURSE_REPO, DB_PROFILE)

            elif cmd == 'status':
                git_status(cfg, COURSE_REPO)

            elif cmd == 'diff':
                git_diff(cfg, COURSE_REPO, PAGER)

            elif cmd == 'difftool':
                git_difftool(cfg, COURSE_REPO)

            elif cmd == 'home':
                open_home(cfg)

            elif cmd == 'modules':
                open_modules(cfg)

            elif cmd == 'repo':
                open_repo(cfg)

            elif cmd == 'config':
                cfg = edit_config(cfg)

            elif cmd == 'yaml':
                edit_build_file(cfg)

            elif cmd == 'guide':
                edit_guide(cfg)

            elif cmd == ('deploy-images', 'deployimages'):
                deploy_images(cfg, COURSE_REPO)

            elif cmd == 'release':
                copy_to_release(cfg)

            elif cmd == 'stage':
                copy_to_staging(cfg)

            elif cmd == 'grep':
                # All the remaining arguments go to grep.
                try:
                    i += 1
                    grep(cfg, args[i:])
                    break
                except IndexError:
                    die('Missing grep arguments.')

            elif cmd == 'sed':
                # All the remaining arguments go to sed.
                try:
                    i += 1
                    sed(cfg, args[i:])
                    break
                except IndexError:
                    die('Missing sed arguments.')

            elif cmd == 'xargs':
                # All the remaining arguments go to the command.
                try:
                    i += 1
                    run_command_on_notebooks(cfg, args[i:])
                    break
                except IndexError:
                    die('Missing argument(s) to xargs.')

            elif cmd == 'set':
                try:
                    i += 1
                    setting = args[i]
                    fields = setting.split('=')
                    if len(fields) != 2:
                        die('Argument to "set" must be of the form CONF=VAL.')
                    key, value = fields
                    value = value.replace('"', '')
                    cfg = configure(cfg, key, value, CONFIG_PATH)
                except IndexError:
                    die('Missing CONF=VAL argument to "set".')

            else:
                die('"{}" is not a valid "course" subcommand.'.format(cmd))

            i += 1

    except CourseError as e:
        printerr(e.message)

if __name__ == '__main__':
    main()
