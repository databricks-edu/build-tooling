# Generate a Databricks DBC file

This directory contains the source code for a tool that will generate a
DBC file from a set of Databricks notebooks. A DBC file is a special
container, a package with one or more notebooks, that can be imported
directly.

Unless you're developing the build tools, you'll never use this tool directly.
It'll be invoked automatically, via either `bdc` or `course`.

For complete documentation on the build tools, please see the [wiki][].

[wiki]: https://github.com/databricks-edu/build-tooling/wiki
