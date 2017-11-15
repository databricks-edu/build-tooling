# bdc - the courseware build tool

This directory contains courseware build tool. (_bdc_ stands for
*B*uild *D*atabricks *C*ourse.) It is a single Python program that attempts to
consolidate all aspects of the curriculum build process. It _does_ rely on some
external artifacts. See below for details.

## Preparing the environment

_bdc_ was written for Python 3, but it will run with Python 2.

### Create a Python virtual environment

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

#### Create a virtual environment

Create a virtual Python environment for the build. You can call it anything
you want, and you can create it any where you want. Let's assume you'll
call it `dbbuild` and put it in your home directory. Here's how to create
the virtual environment.

From a command window, assuming you're in your home directory:

* Linux or Mac: `virtualenv dbbuild`
* Windows: `C:\Python27\Scripts/virtualenv dbbuild`

#### Activate the virtual environment

Once you have the virtual Python environment installed, you'll need to
activate it. **You have to activate the environment any time you create a
new command window.**

(For complete details on using `virtualenv`, see <https://github.com/pypa/virtualenv>.)

* Linux or Mac: `. $HOME/dbbuild/bin/activate`
* Windows: `dbbuild\bin\activate.bat`

### Install _bdc_

Once you've activated the appropriate Python virtual environment, just run
the following commands in this directory:

```
pip install -r requirements.txt
python setup.py install
```

### Install the master parse tool

_bdc_ depends on the [master parse tool](../master_parse), which is written
in Python. Install that tool by running

```
python setup.py install
```

in the `master_parse` source directory.

You need to tell _bdc_ which notebooks to pass through the master parse tool on a per notebook basis in the build.yaml file for a course.

### Install gendbc

_bdc_ also depends on the [gendbc](../gendbc/README.md) tool, which is
written in Scala. Follow the instructions in the _gendbc_ `README.md` file
to install _gendbc_ in the build environment you'll be using.

## Configuration

_bdc_ uses two configuration files:

* a master configuration, which configures _bdc_ itself.
* a per-course configuration

### The master configuration

The _bdc_ configuration file tells _bdc_ about the build environment.
It's a Python ConfigParser configuration. See
<https://docs.python.org/3/library/configparser.html>.

See [bdc.cfg](bdc.cfg) in this directory for a fully-documented example.

### The per-class build file

The per-class build file is a YAML file describing the files that comprise a
particular class. Each class that is to be built will have its own build file.

See [build.yaml](build.yaml) in this directory for a fully-documented example.

## Running the build tool

Just invoke

```
bdc
```

Without any arguments, it'll display a detailed usage message.
