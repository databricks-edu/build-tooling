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

Unless you're actually developing the build tools, you'll probably never run
`master_parse` or `gendbc` manually; `bdc` will do that for you.

## Prerequisites

* Ensure that you have a Python 2 environment (preferably, an activated virtual
  environment).
* Ensure that you have a Java 7 or Java 8 JDK and that `java` is in your path.
  Java 9 is _not supported._ 
* `gendbc` will be installed in `$HOME/local/bin`. Make sure `$HOME/local/bin` 
  is in your path, or your builds will fail.
  
## Quick Links

* [Installing or updating the build tools](#installing-the-build-tools)
* [Using a Docker-based Build Environment](#using-docker)
* [Creating the virtual python environment](#virtual-python-environment)
* [`bdc` Documentation](bdc/README.md), which includes documentation of the build
  file format
* [`master_parse` Documentation](master_parse/README.md), which tells you all
  the cool things the master parser supports within your notebooks.

## Installing the Build Tools

### Using Docker

One of the simplest ways to set your build environment up is to use Docker.
See the [README](docker/README.md) in the `docker` directory for details on
creating and updating a Docker-based build tool environment.

### Installing the Build Tools Manually

#### Virtual Python Environment

_bdc_ is currently limited to Python 2.

While it is possible to build the courseware by installing the necessary
software in the system-installed (or Homebrew-installed) Python, **it is not
recommended**. It's much better to run the build from a dedicated Python
virtual environment. This document describes how to do that. If you want to
use the system version of Python, you're on your own (because it's
riskier).

#### Install `pip`

You'll have to install `pip`, if it isn't already installed. First,
download `get-pip.py` from here:
<https://pip.pypa.io/en/stable/installing/>

Once you have `get-pip.py`, install `pip`.

* If you're on Linux, run this command: `sudo /usr/bin/python get-pip.py`
* If you're on a Mac and _not_ using Homebrew: `sudo /usr/bin/python get-pip.py`
* If you're on a Mac and using a Homebrew-installed Python: `/usr/local/bin/python get-pip.py`
* If you're on Windows and you used the standard installer: `C:\Python27\python get-pip.py`

#### Install `virtualenv`

* Linux: `sudo pip install virtualenv`
* Mac and not using Homebrew: `sudo pip install virtualenv`
* Mac with Homebrew-install Python: `/usr/local/bin/pip install virtualenv`
* Windows: `C:\Python27\Scripts\pip install virtualenv`

##### Create a virtual environment

Create a virtual Python environment for the build. You can call it anything
you want, and you can create it any where you want. Let's assume you'll
call it `dbbuild` and put it in your home directory. Here's how to create
the virtual environment.

From a command window, assuming you're in your home directory:

* Linux or Mac: `virtualenv dbbuild`
* Windows: `C:\Python27\Scripts/virtualenv dbbuild`

##### Activate the virtual environment

Once you have the virtual Python environment installed, you'll need to
activate it. **You have to activate the environment any time you create a
new command window.**

(For complete details on using `virtualenv`, see <https://github.com/pypa/virtualenv>.)

* Linux or Mac: `. $HOME/dbbuild/bin/activate`
* Windows: `dbbuild\bin\activate.bat`


#### Installing the Tools


##### Updating the build tools with `course`

If you've previously installed the tools, and you're not using Docker,
you can just use `course` to reinstall them.


```
course install-tools
```

to install and update the build tools. It will also install `databricks-cli`
for you.

**NOTE**: `course install-tools` does _not_ work for Docker-based
installations. See [Using Docker](#using-docker) if you're using a Docker-based
setup.

##### Installing the build tools manually

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
* `course`

It'll take a few minutes, but it will download and install all three pieces.


## NOTICE

* This software is copyright © 2017-2018 Databricks, Inc., and is released under
  the [Apache License, version 2.0](https://www.apache.org/licenses/). See
  `LICENSE.txt` for details.
* Databricks cannot support this software for you. We use it internally,
  and we have released it as open source, for use by those who are
  interested in building similar kinds of Databricks notebook-based
  curriculum. But this software does not constitute an official Databricks
  product, and it is subject to change without notice.
