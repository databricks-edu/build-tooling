# bdc - the courseware build tool

This directory contains courseware build tool. (_bdc_ stands for
*B*uild *D*atabricks *C*ourse.) It is a single Python program that attempts to
consolidate all aspects of the curriculum build process. It _does_ rely on some
external artifacts. See below for details.

For usage instructions, see [Usage](#usage).

## Preparing the environment

_bdc_ only works on Python 2, because the `--upload` and `--download` features
use the Databricks CLI, which is Python 2-only. 

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
python setup.py install
```

### Install the master parse tool

_bdc_ depends on the
[master parse tool](https://github.com/databricks-edu/build-tooling/tree/master/master_parse).
See the
[master_parse README](https://github.com/databricks-edu/build-tooling/blob/master/master_parse/README.md)
for instructions on how to install that tool. 

You need to tell _bdc_ which notebooks to pass through the master parse tool 
on a per notebook basis in the `build.yaml` file for a course.

### Install gendbc

_bdc_ also depends on the [gendbc](../gendbc/README.md) tool, which is
written in Scala. Follow the instructions in the _gendbc_ `README.md` file
to install _gendbc_ in the build environment you'll be using.

**NOTE**: `bdc` expects to find the `gendbc` binary by searching your PATH.
`gendbc` is installed in `$HOME/local/bin` by default, so make sure that's in
your PATH.

### Install the Databricks CLI

If you're using `bdc --upload` or `bdc --download` (see [Usage](#usage)), you
also need the [Databricks Command Line Interface](https://docs.databricks.com/user-guide/databricks-cli.html).
This tool _only_ supports Python 2; you can install it via:

```
pip install databricks-cli
``` 

See <https://docs.databricks.com/user-guide/databricks-cli.html> for complete
installation and configuration details.

## Configuration

_bdc_ uses a per-course build file that describes the course being built. This
file, conventionally called `build.yaml`, is a YAML file describing the files
that comprise a particular class. Each class that is to be built will have its 
own build file.

See [build.yaml](build.yaml) in this directory for a fully-documented example.

## Usage

Just invoke `bdc` with no arguments for a quick usage message.

`bdc` can be invoke several different ways. Each is described below.

### Getting the abbreviated usage message

Invoke bdc with no arguments to get a quick usage message.

### Getting the full usage message

`bdc -h` or `bdc --help`

### Show only the version

`bdc --version`

### Get a list of the notebooks in a course

`bdc --list-notebooks [build-yaml]`

With this command, `bdc` will list the full paths of all the (source) notebooks 
that comprise a particular course, one per line. `build-yaml` is the path to 
the course's `build.yaml` file, and it defaults to `build.yaml` in the current
directory.

### Build a course

`bdc [-o | --overwrite] [-v | --verbose] [-d DEST | --dest DEST] [build-yaml]`

This version of the command builds a course, writing the results to the
specified destination directory, `DEST`. If the destination directory
doesn't exist, it defaults to `$HOME/tmp/curriculum/<course-id>` (e.g.,
`$HOME/tmp/curriculum/Spark-100-105-1.8.11`).

If the destination directory already exists, the build will fail _unless_ you
also specify `-o` (or `--overwrite`).

If you specify `-v` (`--verbose`), the build process will emit various verbose
messages as it builds the course.

`build-yaml` is the path to the course's `build.yaml` file, and it defaults to 
`build.yaml` in the current directory.

### Upload the course's notebooks to a Databricks shard

You can use `bdc` to upload all notebooks for a course to a Databricks shard.

`bdc --upload shard-path [build-yaml]`

This version of the command gets the list of source notebooks from the build 
file and uploads them to a shard using a layout similar to the build layout.
You can then edit and test the notebooks in Databricks. When you're done
editing, you can use `bdc` to download the notebooks again. (See below.) 

`shard-path` is the path to the folder on the Databricks shard. For instance:
`/Users/foo@example.com/Spark-ML-301`. The folder **must not exist** in the
shard. If it already exists, the upload will abort.

`shard-path` can be relative to your home directory. See
[Relative Shard Paths](#relative-shard-paths), below.

`build-yaml` is the path to the course's `build.yaml` file, and it defaults to 
`build.yaml` in the current directory.

#### Prerequisite
 
This option _requires_ the `databricks-cli` package, which is only
supported on Python 2. You _must_ install and configure the `databricks-cli`
package. The shard to which the notebooks are uploaded is part of the
`databricks-cli` configuration.

See <https://docs.databricks.com/user-guide/databricks-cli.html> for details.

### Download the course's notebooks to a Databricks shard

You can use `bdc` to download all notebooks for a course to a Databricks shard.

`bdc --download shard-path [build-yaml]`

This version of the command downloads the contents of the specified Databricks
shard folder to a local temporary directory. Then, for each downloaded file,
`bdc` uses the `build.yaml` file to identify the original source file and
copies the downloaded file over top of the original source.

`shard-path` is the path to the folder on the Databricks shard. For instance:
`/Users/foo@example.com/Spark-ML-301`. The folder **must exist** in the
shard. If it doesn't exist, the upload will abort.

`shard-path` can be relative to your home directory. See
[Relative Shard Paths](#relative-shard-paths), below.


`build-yaml` is the path to the course's `build.yaml` file, and it defaults to 
`build.yaml` in the current directory.

**WARNING**: If the `build.yaml` points to your cloned Git repository,
**ensure that everything is committed first**. Don't download into a dirty
Git repository. If the download fails or somehow screws things up, you want to
be able to reset the Git repository to before you ran the download.

To reset your repository, use:
 
```
git reset --hard HEAD
```

This resets your repository back to the last-committed state.

#### Prerequisite
 
This option _requires_ the `databricks-cli` package, which is only
supported on Python 2. You _must_ install and configure the `databricks-cli`
package. The shard to which the notebooks are uploaded is part of the
`databricks-cli` configuration.

See <https://docs.databricks.com/user-guide/databricks-cli.html> for details.

### Relative Shard Paths

`--upload` and `--download` can support relative shard paths, allowing you
to specify `foo`, instead of `/Users/user@example.com/foo`, for instance.
To enable relative shard paths, you must do one of the following:

**Set `DB_SHARD_HOME`**

You can set the `DB_SHARD_HOME` environment variable (e.g., in your
`~/.bashrc`) to specify your home path on the shard. For example:

```shell
export DB_SHARD_HOME=/Users/user@example.com
```

**Add a `home` setting to `~/.databrickscfg`**

You can also add a `home` variable to `~/.databrickscfg`, in the `DEFAULT`
section. The Databricks CLI command will ignore it, but `bdc` will honor it.
For example:

```
[DEFAULT]
host = https://trainers.cloud.databricks.com
token = lsakdjfaksjhasdfkjhaslku89iuyhasdkfhjasd
home = /Users/user@example.net
```
