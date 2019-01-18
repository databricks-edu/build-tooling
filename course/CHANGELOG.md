# Change log for `course`

Version 2.0.0

- Completely reimplemented in Python. `bdc` functionality is now invoked via
  function calls, rather than shell command invocation.
- Removed support for the `course stage` and `course release` subcommands.
- Added support for `course which`, which simply displays the currently 
  selected course name.
- `course grep` is now implemented entirely in Python (except for the use of
  the PAGER), so the regular expression you pass to it is processed by the
  Python regular expression parser, not the `grep` one.
- Added a `course showconfig` command to display your course configuration.
- `course deploy-images` has been reduced to a stub, until we figure out how
  it really should work.
- If you use the stock Docker shell aliases, `course` can tell whether it's
  running inside Docker and will refuse to run commands that don't work there.
