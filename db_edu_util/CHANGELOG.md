# notebooktools Change Log

**Version 1.3.0**

- The `db_edu_util.db_cli` package's `databricks` function has been replaced
  with a `Workspace` class that implements the few capabilities we need
  directly against the Databricks REST API.

**Version 1.2.0**

- Converted to Python 3. Added `ExtendedTextWrapper`, to consolidate code
  from different packages.

**Version 1.1.0**

- Renamed package and added `db_cli` package.

**Version 1.0.0**

- Factored out of `gendbc` into its own library.
