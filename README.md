![Travis](https://travis-ci.org/databricks-edu/build-tooling.svg?branch=master)

# build-tools

This directory contains source for the various build tools used during
curriculum development within the Education department at Databricks.

## Subpackages

* `bdc`: *B*uild *D*atabricks *C*ourse: This is the main build tool logic.
  It can be used from the command line or as a library.
* `gendbc`: Create Databricks DBC files from source notebooks. It can be used
  from the command line or as a library.
* `master_parse`: The master notebook parse tool and module. It can be used
  from the command line or as a library.
* `course`: An optional curriculum workflow management tool that sits on top
  of `bdc`. Run `course help` for usage details.
* `db_edu_util`: A library of commonly used functions

For complete documentation on the build tools, please see the [wiki][].

## Docker

The `docker` subdirectory contains Docker-related installation files and
scripts. The build tools are installed into and run from Docker.

## Testing

The `test` subdirectory contains `pytest` tests. To run the tests, first
install `pytest`:

```shell
$ pip install pytest
```

Then, run `python setup.py test`.


## NOTICE

- This software is copyright © 2017-2019 Databricks, Inc., and is released under the Apache License, version 2.0. See LICENSE.txt in the main repository for details.
- Databricks cannot support this software for you. We use it internally, and we have released it as open source, for use by those who are interested in building similar kinds of Databricks notebook-based curriculum. But this software does not constitute an official Databricks product, and it is subject to change without notice.

[wiki]: https://github.com/databricks-edu/build-tooling/wiki

