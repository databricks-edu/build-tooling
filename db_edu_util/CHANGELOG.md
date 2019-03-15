# notebooktools Change Log

**Version 1.6.0**

- Added `Workspace.export_dbc()` to the `databricks` package.

**Version 1.5.0**

- If `home` is not set in `~/.databrickscfg`, and the `DB_SHARD_HOME`
  environment variable isn't set, try to determine home from a
  `username` value in the profile.

**Version 1.4.0**

- The `databricks` package now supports a `home` value in `~/.databrickscfg`
  profiles.

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
