# build-tools

This directory contains source for the various build tools used during
curriculum development within the Education department at Databricks.

* `bdc`: *B*uild *D*atabricks *C*ourse: This is the main build tool.
* `gendbc`: Create Databricks DBC files from the command line.
* `master_parse`: The master notebook parse tool and module.

**Prerequisites**

* Ensure that you have a Python 2 environment (preferably, an activated virtual
  environment).
* Ensure that you have a Java 7 or Java 8 JDK and that `java` is in your path.
  Java 9 is _not supported._ 
* `gendbc` is installed in `$HOME/local/bin`. Make sure `$HOME/local/bin` is in
  your path, or your builds will fail.

## Shortcut Install

Run this command in a Python 2 environment:

```
pip install --upgrade git+https://github.com/databricks-edu/build-tooling
```

It'll take a few minutes, but it will download and install all three pieces.

## Manual install 

Clone this repo, `cd` into it, and type `python setup.py install`.

## Manual install individually

You can also install each tool individually. Consult the README in `bdc`.


## NOTICE

* This software is copyright © 2017 Databricks, Inc., and is released under
  the [Apache License, version 2.0](https://www.apache.org/licenses/). See
  `LICENSE.txt` for details.
* Databricks cannot support this software for you. We use it internally,
  and we have released it as open source, for use by those who are
  interested in building similar kinds of Databricks notebook-based
  curriculum. But this software does not constitute an official Databricks
  product, and it is subject to change without notice.
