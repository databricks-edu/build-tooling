# Change log for `course`

Version 2.0.3:

- Added `course toolversions` command to display versions of `course`,
  `bdc`, `gendbc`, and `master_parse`.

Version 2.0.2:

- No longer bails if a directory in the SELF_PACED_PATH does not exist.
- Added COURSE_DEBUG environment variable, mostly to help debug this thing.

Version 2.0.1

- Fixed a bug that caused an abort in `course work-on` if `COURSE_NAME`
  wasn't already set in the config.
- Updated configuration handling so that `course work-on` _only_ updates
  `COURSE_NAME`-related items in the stored configuration file. All 
  other values in the file are left untouched.
- Updated configuration handling so that values calculated at runtime from
  `COURSE_NAME` (e.g., `COURSE_HOME`, `COURSE_REMOTE_SOURCE`) are ignored
  in the configuration file, even if they're there.

Version 2.0.0

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
