#!/usr/bin/env python

import os
import sys
import bdc
import re
from contextlib import contextmanager
from typing import Generator, Sequence, Pattern
from tempfile import NamedTemporaryFile
from termcolor import colored
from functools import partial

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

VERSION = '2.0.0'
PROG = os.path.basename(sys.argv[0])

CONFIG_PATH = os.path.expanduser("~/.databricks/course.cfg")

USER = os.environ['USER'] # required
PAGER_DEFAULT = 'less --RAW-CONTROL-CHARS'
EDITOR_DEFAULT = 'open -a textedit'
SOURCE_DEFAULT = '_Source'
TARGET_DEFAULT = 'Target'
AWS_PROFILE_DEFAULT = 'default'
DB_PROFILE_DEFAULT = 'DEFAULT'
COURSE_REPO_DEFAULT = os.path.expanduser('~/repos/training')
DB_SHARD_HOME_DEFAULT = '/Users/{}@databricks.com'.format(USER)
DB_CONFIG_PATH_DEFAULT = os.path.expanduser('~/.databrickscfg')
OPEN_DIR_DEFAULT = 'open' # Mac-specific, but can be configured.

USAGE = '''
{0}, version {VERSION}

Usage:
  {0} (-h | --help | help | usage)
  {0} <subcommand> ...
  
Description:
  "course" is a build_and_upload workflow tool, sitting on top of "bdc".
   
  Many subcommands can be chained. For instance:
  
      course upload build_and_upload
      course work-on Delta build_and_upload 

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
  {0} install-tools    * Install the build_and_upload tools.
  {0} work-on <name>     Specify and remember the course to build_and_upload,
                         upload, etc.
  {0} which              Print the name of the currently selected course.
  {0} download           Download from SOURCE
  {0} build_and_upload              Build from local files and upload build_and_upload to TARGET
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
  {0} yaml               Edit the build.yaml.
  {0} config             Edit your course script configuration file.
  {0} showconfig         Print the in-memory configuration, which is the
                         parsed configuration file and possible environment
                         overrides.
  {0} guide            * Open the instructor guide.               
  {0} deploy-images      Deploy the course images to S3. NOTE: This subcommand
                         is a stub. It will be implemented in a later release.
  {0} set VAR=VALUE      Configure and save a setting. Note that the keys are
                         not currently validated, so spelling matters.  
  {0} grep [-i] <re>     Search for a regular expression in course notebooks.
                         The grep is done internally (in Python), so any
                         regular expression accepted by Python is suitable.
                         Use "-i" to specify case-blind matching.
  {0} sed <command>      Search/replace text in notebooks using "sed -i -E".
                         Takes a single "sed" argument and requires a version
                         of "sed" that supports the "-i" (inplace edit) option.
                         (The stock "sed" on the Mac and on Linux both qualify.)

  The following subcommands consume all remaining arguments and end the chain.

  {0} xargs <command>    Run <command> once per notebook.

  The following settings are honored. They are first read from the environment.
  If not there, {0} looks for them in the configuration file, located at
  "{CONFIG_PATH}".
  
  DB_CONFIG_PATH: Path to .databrickscfg
    Default: {DB_CONFIG_PATH_DEFAULT}
  DB_PROFILE: Profile to use within .databrickscfg profile
    Default: {DB_PROFILE_DEFAULT}
  DB_SHARD_HOME: Workspace path for home folder
    Default: {DB_SHARD_HOME_DEFAULT}
  COURSE_NAME: Name of the course you wish to build_and_upload.
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
    CONFIG_PATH=CONFIG_PATH,
    VERSION=VERSION,
    PAGER_DEFAULT=PAGER_DEFAULT,
    DB_CONFIG_PATH_DEFAULT=DB_CONFIG_PATH_DEFAULT,
    DB_PROFILE_DEFAULT=DB_PROFILE_DEFAULT,
    DB_SHARD_HOME_DEFAULT=DB_SHARD_HOME_DEFAULT,
    COURSE_REPO_DEFAULT=COURSE_REPO_DEFAULT,
    AWS_PROFILE_DEFAULT=AWS_PROFILE_DEFAULT,
    SOURCE_DEFAULT=SOURCE_DEFAULT,
    TARGET_DEFAULT=TARGET_DEFAULT,
    EDITOR_DEFAULT=EDITOR_DEFAULT,
    OPEN_DIR_DEFAULT=OPEN_DIR_DEFAULT
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


@contextmanager
def noop(result, *args, **kw):
    '''
    A no-op context manager, with is occasionally useful. Yields its first
    positional parameter. Ignores all the others.

    :param result: what to yield
    :param args:   remaining positional parameters (ignored)
    :param kw:     keyword parameters. Ignored.
    '''
    yield result

def check_for_docker(command):
    if os.environ.get("DOCKER", "") == "true":
        raise CourseError(
            '"{} {}" does not work inside a Docker container.'.format(
              PROG, command
            )
        )


def cmd(shell_command, quiet=False):
    if not quiet:
        print("+ {}".format(shell_command))

    rc = os.system(shell_command)
    if rc != 0:
        raise CourseError('"{}" exited with {}.'.format(shell_command, rc))


def load_config(config_path):
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

    setting_keys_and_defaults = (
        # The second item in each tuple is a default value. If the default
        # value is '', that generally means it can be overridden on the
        # command line (or depends on something else that can be), so it's
        # checked at runtime.
        ('DB_CONFIG_PATH', DB_CONFIG_PATH_DEFAULT),
        ('DB_PROFILE', DB_PROFILE_DEFAULT),
        ('DB_SHARD_HOME', DB_SHARD_HOME_DEFAULT),
        ('PREFIX', ''),                              # set later
        ('COURSE_NAME', None),                       # can be overridden
        ('COURSE_REPO', COURSE_REPO_DEFAULT),
        ('COURSE_HOME', None),                       # depends on COURSE_NAME
        ('COURSE_YAML', None),                       # depends on COURSE_NAME
        ('COURSE_MODULES', None),                    # depends on COURSE_NAME
        ('COURSE_REMOTE_SOURCE', None),              # depends on COURSE_NAME
        ('COURSE_REMOTE_TARGET', None),              # depends on COURSE_NAME
        ('COURSE_AWS_PROFILE',  AWS_PROFILE_DEFAULT),
        ('SOURCE', SOURCE_DEFAULT),
        ('TARGET', TARGET_DEFAULT),
        ('EDITOR', EDITOR_DEFAULT),
        ('PAGER', PAGER_DEFAULT),
        ('OPEN_DIR', OPEN_DIR_DEFAULT),
    )

    # Apply environment overrides. Then, check for missing ones where
    # appropriate, and apply defaults.
    for e, default in setting_keys_and_defaults:
        v = os.environ.get(e)
        if v is not None:
            cfg[e] = v

        if (cfg.get(e) is None) and default:
            cfg[e] = default

    return cfg


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


def update_config(cfg):
    # type: (dict) -> dict
    '''
    Update the configuration, setting values that depend on course name,
    which is assumed to be set in the configuration.

    :param cfg: current configuration

    :return: possibly adjusted configuration
    '''
    course_name = cfg['COURSE_NAME']
    from os.path import join, normpath

    adj = cfg.copy()
    repo = adj['COURSE_REPO']

    self_paced = get_self_paced_courses(repo)
    prefix = 'Self-Paced' if course_name in self_paced else ''

    adj['PREFIX'] = prefix
    adj['COURSE_HOME'] = normpath(join(repo, 'courses', prefix, course_name))
    adj['COURSE_YAML'] = join(adj['COURSE_HOME'], 'build.yaml')
    adj['COURSE_MODULES'] = join(repo, 'modules', prefix,course_name)
    adj['COURSE_REMOTE_SOURCE'] = '{}/{}/{}'.format(
        adj['DB_SHARD_HOME'], adj['SOURCE'], course_name
    )
    adj['COURSE_REMOTE_TARGET'] = '{}/{}/{}'.format(
        adj['DB_SHARD_HOME'], adj['TARGET'], course_name
    )


    return adj


def build_file_path(cfg):
    # type: (dict) -> str
    res = cfg.get('COURSE_YAML')
    if not res:
        res = os.path.join(cfg['COURSE_HOME'], 'build.yaml')

    return res


def configure(cfg, key, value, config_path):
    # type: (dict, str, str, str) -> dict
    cfg[key] = value
    # Don't update from the in-memory config, because it might not match
    # what's in the file. (It can be modified on the fly, based on the command
    # line, and those ephemeral changes should not be saved.)
    stored_cfg = load_config(config_path)
    stored_cfg[key] = value
    with open(config_path, 'w') as f:
        for k, v in stored_cfg.items():
            f.write('{}={}\n'.format(k, v))

    return cfg


def work_on(cfg, course_name, config_path):
    # type: (dict, str, str) -> dict
    return configure(cfg, 'COURSE_NAME', course_name, config_path)


def show_course_name(cfg):
    # type: (dict) -> None
    print(cfg['COURSE_NAME'])


def clean(cfg):
    # type: (dict) -> None
    db_profile = cfg['DB_PROFILE']
    course_name = cfg['COURSE_NAME']
    remote_target = cfg['COURSE_REMOTE_TARGET']

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


def clean_source(cfg):
    # type: (dict) -> None
    db_profile = cfg['DB_PROFILE']
    course_name = cfg['COURSE_NAME']
    remote_source = cfg['COURSE_REMOTE_SOURCE']

    cmd('databricks --profile "{}" workspace mkdirs "{}"'.format(
        db_profile, remote_source
    ))
    cmd('databricks --profile "{}" workspace rm --recursive "{}"'.format(
        db_profile, remote_source
    ))


def download(cfg):
    # type: (dict) -> None
    course_repo = cfg['COURSE_REPO']
    db_profile = cfg['DB_PROFILE']
    course_name = cfg['COURSE_NAME']

    bdc.bdc_download(build_file=build_file_path(cfg),
                     shard_path=cfg['COURSE_REMOTE_SOURCE'],
                     databricks_profile=db_profile,
                     verbose=False)


def upload(cfg):
    # type: (dict) -> None
    course_repo = cfg['COURSE_REPO']
    db_profile = cfg['DB_PROFILE']
    course_name = cfg['COURSE_NAME']

    bdc.bdc_upload(build_file=build_file_path(cfg),
                   shard_path=cfg['COURSE_REMOTE_SOURCE'],
                   databricks_profile=db_profile,
                   verbose=False)


def import_dbcs(cfg, build_dir):
    # type: (dict, str) -> None

    remote_target = cfg['COURSE_REMOTE_TARGET']
    course_name = cfg['COURSE_NAME']
    db_profile = cfg['DB_PROFILE']
    course_repo = cfg['COURSE_REPO']

    def import_dbc(dbc):
        # type: (str) -> None
        '''
        Import a single DBC.

        Assumes (a) the working directory is the build_and_upload output directory, and
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
            clean(cfg)
            cmd('databricks --profile {} workspace mkdirs {}'.format(
                db_profile, remote_target
            ))
            for dbc in dbcs:
                import_dbc(dbc)


def build_only(course_name, build_file):
    # type: (str, str) -> None
    print("\nBuilding {}".format(course_name))
    bdc.bdc_build_course(build_file,
                         dest_dir='',
                         overwrite=True,
                         verbose=False)


def build_and_upload(cfg):
    # type: (dict) -> None
    course_name = cfg['COURSE_NAME']

    build_file = build_file_path(cfg)
    if not os.path.exists(build_file):
        die('Build file "{}" does not exist.'.format(build_file))
    build_only(course_name, build_file)
    build_dir = bdc.bdc_output_directory_for_build(build_file)
    import_dbcs(cfg, build_dir)


def install_tools(cfg):
    # type: (dict) -> None
    check_for_docker("install-tools")
    cmd('pip install git+https://github.com/$FORK/build-tooling')


def browse_directory(cfg, path, subcommand):
    # (dict, str, str) -> None
    check_for_docker(subcommand)
    cmd('{} "{}"'.format(cfg['OPEN_DIR'], path))


def edit_file(cfg, path, subcommand):
    # type: (dict, str, str) -> None
    cmd('{} "{}"'.format(cfg['EDITOR'], path))


def edit_config(cfg):
    # type: (dict) -> dict
    edit_file(cfg, CONFIG_PATH, 'config')
    return load_config(CONFIG_PATH)


def git_status(cfg):
    # type: (dict) -> None
    course_repo = cfg['COURSE_REPO']
    print('+ cd {}'.format(course_repo))
    with working_directory(course_repo):
        cmd("git status")


def git_diff(cfg):
    # type: (dict) -> None
    course_repo = cfg['COURSE_REPO']
    pager = cfg['PAGER']
    with working_directory(course_repo):
        if len(pager.strip()) == 0:
            cmd("git status")
        else:
            cmd("git status | {}".format(pager))


def git_difftool(cfg):
    # type: (dict) -> None
    course_repo = cfg['COURSE_REPO']
    check_for_docker("difftool")
    with working_directory(course_repo):
        cmd("git difftool --tool=opendiff --no-prompt")


def deploy_images(cfg):
    # type: (dict) -> None
    print("*** WARNING: 'deploy-images' is not yet implemented.")


def grep(cfg, pattern, case_blind=False):
    # type: (dict, str, bool) -> None

    def grep_one(path, r, out):
        # type: (str, Pattern, file) -> None
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

                # Colorize the match.
                s = m.start()
                e = m.end()
                matches.append(line[:s] + colored(line[s:e], 'green') + line[e:])

        if matches:
            out.write('\n\n=== {}\n\n'.format(printable_path))
            out.write(''.join(matches))

    r = None
    try:
        flags = 0 if not case_blind else re.IGNORECASE
        r = re.compile(pattern, flags=flags)
    except Exception as e:
        die('Cannot compile regular expression "{}": {}'.format(
            pattern, e.message
        ))

    from subprocess import Popen, PIPE
    pager = cfg.get('PAGER')
    if pager:
        opener = NamedTemporaryFile
    else:
        opener = partial(noop, sys.stdout)

    with opener(mode='w') as out:
        for nb in bdc.bdc_get_notebook_paths(build_file_path(cfg)):
            grep_one(nb, r, out)

        out.flush()

        if pager:
            # In this case, we know we have a NamedTemporaryFile
            p = Popen("{} <{}".format(pager, out.name), shell=True)
            p.wait()


def sed(cfg, sed_cmd):
    # type: (dict, str) -> None
    for nb in bdc.bdc_get_notebook_paths(build_file_path(cfg)):
        # Quote the argument.
        quoted = ''
        q = sed_cmd[0]
        if q in ('"', "'"):
            # Already quoted, hopefully.
            if sed_cmd[-1] != q:
                raise CourseError(
                'Mismatched quotes in sed argument: {}'.format(sed_cmd)
                )
            quoted = sed_cmd
        elif ('"' in sed_cmd) and ("'" in sed_cmd):
            raise CourseError(
                ('"sed" argument cannot be quoted, since it contains ' +
                 'single AND double quotes: {}').format(sed_cmd)
             )
        elif "'" in sed_cmd:
            quoted = '"' + sed_cmd + '"'
        else:
            quoted = "'" + arg + "'"

        cmd('sed -E -i "" -e {} "{}"'.format(quoted, nb))


def run_command_on_notebooks(cfg, args):
    # type: (dict, Sequence[str]) -> None
    pass


# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------

def main():
    try:
        cfg = load_config(CONFIG_PATH)

        # Update the environment, for subprocesses we need to invoke.

        os.environ['EDITOR'] = cfg['EDITOR']
        os.environ['PAGER'] = cfg['PAGER']

        # Loop over the argument list, since we need to support chaining some
        # commands (e.g., "course download build_and_upload"). This logic emulates
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
            cfg = update_config(cfg)

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
                    work_on(cfg, args[i], CONFIG_PATH)
                except IndexError:
                    die('Expected course name after "work-on".')

            elif cmd == 'which':
                show_course_name(cfg)

            elif cmd == 'install_tools':
                install_tools(cfg)

            elif cmd == 'download':
                download(cfg)

            elif cmd == 'upload':
                upload(cfg)

            elif cmd == 'build':
                build_and_upload(cfg)

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
                # All the remaining arguments go to grep.
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
                    break
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

            elif cmd == "showconfig":
                hdr = "Current configuration"
                print('-' * len(hdr))
                print(hdr)
                print('-' * len(hdr))
                for key in sorted(cfg.keys()):
                    print('{}="{}"'.format(key, cfg[key]))

            else:
                die('"{}" is not a valid "course" subcommand.'.format(cmd))

            i += 1

    except CourseError as e:
        printerr(e.message)

    except KeyboardInterrupt:
        printerr('\n*** Interrupted.')

if __name__ == '__main__':
    main()
