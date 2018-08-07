# build-tools

This directory contains source for the various build tools used during
curriculum development within the Education department at Databricks.

* `bdc`: *B*uild *D*atabricks *C*ourse: This is the main build tool.
* `gendbc`: Create Databricks DBC files from the command line.
* `master_parse`: The master notebook parse tool and module.

## Prerequisites

* Ensure that you have a Python 2 environment (preferably, an activated virtual
  environment).
* Ensure that you have a Java 7 or Java 8 JDK and that `java` is in your path.
  Java 9 is _not supported._ 
* `gendbc` will be installed in `$HOME/local/bin`. Make sure `$HOME/local/bin` 
  is in your path, or your builds will fail.
  
## Quick Links

* [Creating the virtual python environment](#virtual_python_environment)
* [Installing the build tools](#installing_the_build_tools)

## Virtual Python Environment

_bdc_ is currently limited to Python 2.

While it is possible to build the courseware by installing the necessary
software in the system-installed (or Homebrew-installed) Python, **it is not
recommended**. It's much better to run the build from a dedicated Python
virtual environment. This document describes how to do that. If you want to
use the system version of Python, you're on your own (because it's
riskier).

### Install `pip`

You'll have to install `pip`, if it isn't already installed. First,
download `get-pip.py` from here:
<https://pip.pypa.io/en/stable/installing/>

Once you have `get-pip.py`, install `pip`.

* If you're on Linux, run this command: `sudo /usr/bin/python get-pip.py`
* If you're on a Mac and _not_ using Homebrew: `sudo /usr/bin/python get-pip.py`
* If you're on a Mac and using a Homebrew-installed Python: `/usr/local/bin/python get-pip.py`
* If you're on Windows and you used the standard installer: `C:\Python27\python get-pip.py`

### Install `virtualenv`

* Linux: `sudo pip install virtualenv`
* Mac and not using Homebrew: `sudo pip install virtualenv`
* Mac with Homebrew-install Python: `/usr/local/bin/pip install virtualenv`
* Windows: `C:\Python27\Scripts\pip install virtualenv`

### Create a virtual environment

Create a virtual Python environment for the build. You can call it anything
you want, and you can create it any where you want. Let's assume you'll
call it `dbbuild` and put it in your home directory. Here's how to create
the virtual environment.

From a command window, assuming you're in your home directory:

* Linux or Mac: `virtualenv dbbuild`
* Windows: `C:\Python27\Scripts/virtualenv dbbuild`

### Activate the virtual environment

Once you have the virtual Python environment installed, you'll need to
activate it. **You have to activate the environment any time you create a
new command window.**

(For complete details on using `virtualenv`, see <https://github.com/pypa/virtualenv>.)

* Linux or Mac: `. $HOME/dbbuild/bin/activate`
* Windows: `dbbuild\bin\activate.bat`


## Installing the Build Tools

If you have never installed the tools in your virtual Python environment, run
this command:

```
pip install git+https://github.com/databricks-edu/build-tooling
```

If you have installed the tools before, run:

```
pip install --upgrade git+https://github.com/databricks-edu/build-tooling
```

This installation script will install:

* `bdc`
* `master_parse`
* `gendbc`
* `databricks-cli`

It'll take a few minutes, but it will download and install all three pieces.

## Manual install 

Clone this repo, `cd` into it, and type `python setup.py install`.


## NOTICE

* This software is copyright © 2017-2018 Databricks, Inc., and is released under
  the [Apache License, version 2.0](https://www.apache.org/licenses/). See
  `LICENSE.txt` for details.
* Databricks cannot support this software for you. We use it internally,
  and we have released it as open source, for use by those who are
  interested in building similar kinds of Databricks notebook-based
  curriculum. But this software does not constitute an official Databricks
  product, and it is subject to change without notice.
