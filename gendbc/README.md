# Generate a Databricks DBC file

This directory contains the source code for a tool that will generate a
DBC file from a set of Databricks notebooks. A DBC file is a special
container, a package with one or more notebooks, that can be imported
directly.

Unless you're developing the build tools, you'll never use this tool directly.
It'll be invoked automatically, via either `bdc` or `course`.

For complete documentation on the build tools, please see the [wiki][].

## NOTICE

- This software is copyright © 2017-2019 Databricks, Inc., and is released under the Apache License, version 2.0. See LICENSE.txt in the main repository for details.
- Databricks cannot support this software for you. We use it internally, and we have released it as open source, for use by those who are interested in building similar kinds of Databricks notebook-based curriculum. But this software does not constitute an official Databricks product, and it is subject to change without notice.

[wiki]: https://github.com/databricks-edu/build-tooling/wiki
