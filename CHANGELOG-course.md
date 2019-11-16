# Change log for `course`

**Version 2.8.0**

- course.cfg variables can override OS environment if `FORCE_[VARNAME]` flag is set.

**Version 2.7.1**

- Fixed a bug: `course build` failed to import the built DBC if build profiles
  are not being used.
- Moved `working_directory()` function to `db_edu_util` library, to remove
  duplication between `bdc` and `course`.

**Version 2.7.0**

- Added ability to tag the Git repo with a tag constructed from the current
  course's name and version. See 
  [Issue #78](https://github.com/databricks-edu/build-tooling/issues/78)

**Version 2.6.0**

- `course --name CourseName` now works again. Addresses
  [Issue #85](https://github.com/databricks-edu/build-tooling/issues/85).
- `course diff` now invokes `git diff`, not `git status`. Partially addresses
  [Issue #82](https://github.com/databricks-edu/build-tooling/issues/82).

**Version 2.5.0**

- Added `databricks_cli` version back to `course toolversions`.

**Version 2.4.0**

- Removed direct support for `DB_SHARD_HOME` and the `home` configuration 
  option, since the `databricks` package supports both.
- Now creates directory `~/.databricks` if it doesn't already exist. This fix
  addresses [Issue #70](https://github.com/databricks-edu/build-tooling/issues/70).

**Version 2.3.0**

- Updated to use new `databricks.Workspace` class to interact with the 
  Databricks workspace.
- `course install-tools` is now deprecated, because it isn't possible to update
  a Docker container from within itself.

**Version 2.2.0**

- Added ability to specify build file with `course -f` or `course --build-file`.
  e.g., `course -f build-ilt.yaml build`

**Version 2.1.0**

- Now implemented in Python 3.

**Version 2.0.7**

- Changed to work with new `db_edu_util` library, which contains 
  `notebooktools` and other goodies.
- Now runs the `databricks_cli` commands via a function call, rather than
  a shell command.

**Version 2.0.6**

- `course toolversions` now display the version of the `notebooktools`
  library.

**Version 2.0.5**

- `DB_SHARD_HOME` is now required, either in the configuration file or in
  the environment. The code can't reasonably infer a default, and any default
  it assumes is likely to be confusing. 

**Version 2.0.4**

- Restored ability to override `COURSE_YAML` in the configuration file. If
  it isn't in the configuration file, it's calculated from `COURSE_NAME`.

**Version 2.0.3**

- Added `course toolversions` command to display versions of `course`,
  `bdc`, `gendbc`, and `master_parse`.

**Version 2.0.2**

- No longer bails if a directory in the SELF_PACED_PATH does not exist.
- Added COURSE_DEBUG environment variable, mostly to help debug this thing.

**Version 2.0.1**

- Fixed a bug that caused an abort in `course work-on` if `COURSE_NAME`
  wasn't already set in the config.
- Updated configuration handling so that `course work-on` _only_ updates
  `COURSE_NAME`-related items in the stored configuration file. All 
  other values in the file are left untouched.
- Updated configuration handling so that values calculated at runtime from
  `COURSE_NAME` (e.g., `COURSE_HOME`, `COURSE_REMOTE_SOURCE`) are ignored
  in the configuration file, even if they're there.

**Version 2.0.0**

- Completely reimplemented in Python. `bdc` functionality is now invoked via
  function calls, rather than shell command invocation.
- Removed support for the `course stage` and `course release` subcommands.
- Added `course which`, which simply displays the current course name. 
- Added `course showconfig` command to display your course configuration.
- Added `course build-local` to build the course, but not upload the DBCs.
- Added `course upload-built` to upload a course built by `build-local`.
  (You probably won't use this one much, but it rounds things out.)
- `course grep` is now implemented entirely in Python (except for the use of
  the PAGER), so the regular expression you pass to it is processed by the
  Python regular expression parser, not the `grep` one.
- `course deploy-images` has been reduced to a stub, until we figure out how
  it really should work.
- If you use the stock Docker shell aliases, `course` can tell whether it's
  running inside Docker and will refuse to run commands that don't work there.
