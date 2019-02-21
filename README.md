# build-tools

This directory contains source for the various build tools used during
curriculum development within the Education department at Databricks.

* `bdc`: *B*uild *D*atabricks *C*ourse: This is the main build tool. See
  the `bdc` [README](bdc/README.md) for full details.
* `gendbc`: Create Databricks DBC files from the command line.  See
  the `gendbc` [README](gendbc/README.md) for full details.
* `master_parse`: The master notebook parse tool and module. See the
  `master_parse` [README](master_parse/README.md) for full details.
* `course`: An optional curriculum workflow management tool that sits on top
  of `bdc`. Run `course help` for usage details.

For complete documentation on the build tools, please see the [wiki][].

## NOTICE

- This software is copyright © 2017-2019 Databricks, Inc., and is released under the Apache License, version 2.0. See LICENSE.txt in the main repository for details.
- Databricks cannot support this software for you. We use it internally, and we have released it as open source, for use by those who are interested in building similar kinds of Databricks notebook-based curriculum. But this software does not constitute an official Databricks product, and it is subject to change without notice.

[wiki]: https://github.com/databricks-edu/build-tooling/wiki

