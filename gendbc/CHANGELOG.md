# Change Log for gendbc

**Version 2.0.1**

- Fixed a bug: The generated DBC JSON for Python notebooks caused Databricks
  to throw a fit, because the notebook language was encoded as "py", rather
  than "python."

**Version 2.0.0**

- Completely reimplemented in Python, instead of Scala.

**Version 1.4.0**

- Added `--version` command line option.
- Updated various dependencies.

**Version 1.3.3**

- Emit tool name as prefix, where possible, on verbose and error messages.
- Wrap usage output, for readability.

**Version 1.3.2**

- Fixed common path prefix bug in DBC generation.
- Updated `build.sbt` to remove SBT deprecation warnings.
- Added change log.
