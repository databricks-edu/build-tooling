# gendbc

**Warning: This tool is being superseded. It's still used by the build, but
it is _not_ being maintained moving forward.**

## Introduction

This Scala program takes, as input, a directory that contains Scala, Python,
SQL or R notebooks that have been exported, _in source form_, from Databricks.
The program then parses the notebooks, converts them to DBC JSON, and produces
a DBC archive suitable for upload to a Databricks shard.

## Restrictions

The JSON encoding logic in this tool relies on the information in
<https://github.com/databricks/training/blob/master/devops/courseware_build/dbc_format.md>,
as well as information gleaned from reverse-engineering the DBC JSON. The JSON
generation is entirely within this tool; the code does _not_ currently use a
an official Databricks library.

Similarly, the notebook-parsing logic also doesn't use any code provided by
Engineering; it relies solely on the observable format of a source-exported
Databricks notebook.

Because of its reverse-engineered nature, _gendbc_ is potentially fragile.

* If Engineering changes the format of the DBC JSON, _gendbc_ could break,
  failing to produce valid DBC files.
* If Engineering changes the format of source-exported notebooks, _gendbc_
  could break, because of a failure to parse the notebooks.

## Installing

You _can_ run the tool with `java -jar`, but it's easier to install the
front-end script. This section talks about both methods.

**NOTE**: In all cases, you _must_ have a Java Development Kit (JDK),
preferably 1.8, installed and available in your PATH.

### Installing the script

#### On Unix or Mac OS X

To build and install the `gendbc` script, simply run the following
command within the top-level directory:

```
bin/activator install
```

**NOTE**: You might need to add the `-J-XX:MaxPermSize=1g` option, if you're building
with JDK 1.7 or earlier.

This command will build a fat jar, install the jar in `$HOME/local/libexec`,
and generate a shell script called `gendbc` in `$HOME/local/bin`.

You can change the installation directory by setting the `INSTALL_DIR`
environment variable. For example, to install `gendbc` in `/usr/local/bin`,
use this command:

```
INSTALL_DIR=/usr/local bin/activator install
```

Provided the installation `bin` directory is in your path, you should be able
to run the tool as:

```
gendbc
```

Run without arguments to see the usage.

#### On Windows

Since the Lightbend Activator script is not reliable on Windows, to build on
Windows, download [SBT](http://scala-sbt.org) (version 0.13.x) and install it.
Then, within this repo's top-level directory, run:

```
sbt install
```

**NOTE**: You might need to add the `-J-XX:MaxPermSize=1g` option, if you're
building with JDK 1.7 or earlier.

This command will build a fat jar, install the jar in `%HOME%\local\libexec`,
and generate a shell script called `gendbc.bat` in `$HOME\local\bin`.

You can change the installation directory by setting the `INSTALL_DIR`
environment variable. For example, to install `gendbc` in
`C:\Program Files\gendbc\bin`, use these commands:

```
set INSTALL_DIR=C:\Program Files\gendbc
sbt install
```

Provided the installation `bin` directory is in your path, you should be able
to run the tool as:

```
gendbc
```

Run without arguments to see the usage.

### Installing the jar _only_

If you don't want to use the `gendbc` script, you _can_ just install the
jar. To do that, run one of the following commands:

**Unix or Mac**:

```
bin/activator assembly
```

**Windows**

```
sbt assembly
```

The resulting fat jar will be in `target/scala_2.11/gendbc-assembly-1.x.y.jar`,
where `1.x.y` is the current version number.

Simply copy that jar wherever you want, and run with:

```
java -jar /path/to/gendbc-assembly-1.x.y.jar       # Unix or Mac
java -jar \path\to\gendbc-assembly-1.x.y.jar       # Windows
```

Run without arguments to see the usage.
