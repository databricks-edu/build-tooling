# bdc - the courseware build tool

This directory contains courseware build tool. (_bdc_ stands for
*B*uild *D*atabricks *C*ourse.) It is a single Python program that attempts to
consolidate all aspects of the curriculum build process. It _does_ rely on some
external artifacts. See below for details.

Quick links:

* [Command line usage](#usage)
* [Installation](#installation)
* [Build file syntax](#build-file)

For usage instructions, see . For a description of the
build file syntax, see [Build File](#build_file).

## Installation

#### Install the build tools

Once you've activated the appropriate Python virtual environment,
see the [master README](../README.md) for a single command that will install
all the build tools.

## Build File

_bdc_ uses a per-course build file that describes the course being built. This
file, conventionally called `build.yaml`, is a YAML file describing the files
that comprise a particular class. Each class that is to be built will have its 
own build file.

See [build.yaml][] in this directory for a fully-documented example.

This section describes each section and configuration item in the build file.

### Tool versions

Two **required** settings control the minimum versions of both `bdc` and
the master parser are required for a given build file. Both tools use
[semantic versioning](https://semver.org), so version numbers are of the
form _major.minor.patch_ (e.g., 1.19.3). Since patch versions should
always be backward-compatible, `bdc` only looks at the major and minor
numbers. (Thus, the values "1.19.3", "1.19" and "1.19.0" are the same: They
all set the minimum version to "1.19".)

**NOTE**: These values _must_ be quoted, so they don't get interpreted as
floating point numbers by the YAML parser!

**`bdc_min_version`** sets the minimum version of `bdc` required to run the
build. Using an older version of `bdc` will cause an automatic build failure.

**`master_parse_min_version`** sets the minimum version of the master parser
required to run the build. Using an older version of `master_parse` will cause 
an automatic build failure.

### Course info

The `course_info` section defines information about the course. It contains
the following fields:

- `name`: (REQUIRED) The name of the course (e.g., "Databricks-Delta"). The 
  name should not have any white space, as it is used to construct file names.
- `version`: (REQUIRED) The (semantic) version number of the course (e.g., 
  "1.0.1").
- `type`: (REQUIRED) The course type. Legal values are "ilt" (for instructor-led
  materials) and "self-paced".
- `copyright_year`: (OPTIONAL) Copyright year of the course materials. Defaults
  to the current year.
- `class_setup`: (OPTIONAL) Path to the class setup instructions (for site
  managers of a given training site) on how to prepare the classroom 
  environment. For Databricks classes, a survey exists for this purpose. 
  However, for partners, this document summarizes the minimum needs. The path
  relative to the directory containing _build file_. If defined, this file will 
  be copied to the top of the destination directory or directories. Only
  meaningful for ILT classes.
- `schedule`: (OPTIONAL) Path to a document that describes the recommended
  teaching schedule for the class. Only meaningful for ILT classes.
- `prep`: (OPTIONAL) Path to a Markdown document that outlines any instructor
  preparation that must be done before teaching the class. The file, if
  specified, is copied to `InstructorFiles/Preparation.md` under the target
  directory. An HTML version is also generated there. Only meaningful for
  ILT classes.
- `deprecated`: (OPTIONAL) If present and true, this field marks the course
  as deprecated (i.e., no longer used). Attempts to build the course will
  fail. Default: false  

Example sections:

```yaml
course_info:
  name: Databricks-Delta
  version: 1.0.0
  type: self-paced
```

```yaml
course_info:
  name: Spark-ILT
  version: 2.1.2-SNAPSHOT
  type: ilt 
```

### Build Profiles

Some courses need to be slightly different for AWS and Azure. The master
parser already supports conditional tags (`AZURE_ONLY` and `AMAZON_ONLY`),
but they must be enabled, and they're not appropriate for all courses.

To enable AWS and Amazon build profiles, set `use_profiles` to `true`.

If `use_profiles` is `true`:

- The course is generated twice, once for Amazon (suppressing any notebook
  cells marked `AZURE_ONLY`) and once for Azure (suppressing any cells marked
  `AMAZON_ONLY`).
- The two separate builds are written to `azure` and `amazon` subdirectories
  underneath the build destination directory.
- Two separate [bundles](#bundles) are generated, if bundles are enabled.

If `use_profiles` is `false`, the course is generated once, into the
destination directory.

`use_profiles` is `false`, by default.

See also `only_in_profile` in the [Notebooks][#notebooks] section.

### Output Generation

Several settings help define the layout of the final built course.

- `student_dbc`:  

### Notebooks

Source notebooks listed in the `build.yaml` are parsed, run through the master
parser, converted into multiple output notebooks, and, ultimately, gathered
into a single Databricks DBC file for easy import.

This section discusses the various notebook-related settings in `build.yaml`.

#### DBC files

`bdc` generates two 

#### The top-most DBC folder

A DBC file is a special kind of zip file containing JSON-encoded notebooks.
By default, when `bdc` generates the final DBC files, it places all notebooks
under a top-level directory named after the course. You can change that
strategy by setting the `top_dbc_folder_name` variable.

The following variables can be substituted into this value:

| Variable            | Meaning
| ------------------- | -------
| `${course_name}`    | the course name, from `course_info.name`
| `${course_version}` | the course version, from `course_info.version`
| `${course_id}`      | convenience variable: same as `${course_name}-${course_version}`
| `${profile}`        | the name of the current build profile ("amazon" or "azure"), if any
| your variables      | any [custom variables you define](#where-do-variables-come-from)

Examples:

```
top_dbc_folder_name: Course-${course_name}-${course_version}
top_dbc_folder_name: Lessons
top_dbc_folder_name: ${course_name}  # same as the default
```

### Bundles

### Variable substitution

Many (but not all) items in a `build.yaml` file support variable substitution.
This section discusses that feature. 

#### Where do variables come from?

Variables currently come from several places:

- There are variables that are built into `bdc`, such as `${notebook_type}`,
  `${basename}`, and others.

- You can define build-wide variables of your own in the "variables" section
  in `build.yaml`. (These variables cannot override built-in variables.)
  For example, if you define the following `variables` section, you can
  substitute `${foo}` wherever custom variables are supported:
```
variables:
  foo: This string will replace ${foo}
```  
  
- You can define per-notebook variables in a "variables" section in each
  notebook. These variables can also override build-wide globals, on a
  per-notebook basis, though they cannot override `bdc` built-ins.

- You can define variables for all notebooks in the `notebook_defaults`
  section.

See the sample [build.yaml][] for full details.

#### Variable Substitution Syntax

The variable substitution syntax is Unix shell-like:

- `$var` substitutes the value of a variable called "var"
- `${var}` substitute the value of a variable called "var"

The second form is useful when you need to ensure that a variable's name
doesn't get mashed together with a subsequent non-white space string, e.g.:

- `${var}foo` substitutes the value of "var" preceding the string "foo"
- `$varfoo` attempts to substitute the value of "varfoo"

To escape a `$`, use `$$` or `\$`.

To escape a backslash, use `\\`.

##### Variable names

Legal variable names consist of alphanumeric and underscore characters only.

##### Subscripting and slicing

Variables can be subscripted and sliced, Python-style, as long as they use the
brace (`${var}`) syntax.

Examples: 

- `${foo[0]}`
- `${foo[-1]}`
- `${foo[2:3]}`
- `${foo[:]}`
- `${foo[:-1]}`
- `${foo[1:]}`

Subscripts are interpreted as in Python code, except that the "stride"
capability isn't supported. (That is, you cannot use `${foo[0:-1:2]`
to slice through a value with index jumps of 2.)

One difference: If the final subscript is too large, it's sized down. For 
instance, given the variable `foo` set to `"ABCDEF"`, the substitution 
`${foo[100]}` yields `"F"`, and the substitution `${foo[1:10000]}` yields
`"BCDEF"`. As a special case, subscripting an empty variable always
yields an empty string, regardless of the subscript.

##### Inline ("ternary") IF

The variable syntax supports a C-like "ternary IF" statement. The general
form is:

```
${variable == "SOMESTRING" ? "TRUESTRING" : "FALSESTRING"}
${variable != "SOMESTRING" ? "TRUESTRING" : "FALSESTRING"}
```

Rules:

1. The braces are _not_ optional.
2. The strings (`SOMESTRING`, `TRUESTRING` and `FALSESTRING`) _must_ be
   surrounded by double quotes. Single quotes are _not_ supported.
3. Simple variable substitutions (`$var`, `${var}`, `${var[0]}`, etc.)
   are permitted _within_ the quoted strings, but the quotes are still required.
   Ternary IFs and inline editing are _not_ supported within a ternary IF.
4. The white space is optional.
5. When using a ternary IF substitution, your _must_ surround the entire string
   in **single quotes**. The string has to be quoted to prevent the YAML
   parser from getting confused by the embedded ":" character.
6. To use a literal double quote within one of the ternary expressions,
   escape it with `\"`.

**Examples**:

Substitute the string "FOO" if variable "foo" equals "foo". Otherwise,
substitute the string "BAR":

```
${foo == "foo" ? "FOO" : "BAR"}
```

Substitute the string "-solution" if variable "notebook_type" is "answers".
Otherwise, substitute nothing:

```
${notebook_type=="answers"?"-solution":""}
```

Variables within the ternary expressions:
```
${foo == "$bar" ? "It matches $$bar." : "It's $foo, not $bar"}
         ^    ^   ^                 ^   ^                   ^
         Note that the double quotes are REQUIRED

${x == "abc${foo}def" ? "YES" : "NO."}
```

Double quote (") as part of a value being tested:

```
${foo == "\"" ? "QUOTE" : "NOT QUOTE"}
```

##### Inline editing

`bdc` supports basic sed-like editing on a variable's value, using a syntax
that's vaguely reminiscent (but somewhat more readable) than the Bash
variable-editing syntax.

`bdc` supports a simple inline editing capability in variable substitution,
reminiscent of the `bash` syntax (but a little easier to read). The basic
syntax is:

```
${var/regex/replacement/flags}
${var|regex|replacement|flags}
```

Note that only two delimiters are supported, "|" and "/", and they _must_
match. 

By default, the first instance of the regular expression in the variable's
value is replaced with the replacement. (You can specify a global replacement
with a flag. See `flags`, below.)

**`regex`**

`regex` is a [standard Python regular expression](https://docs.python.org/2/library/re.html#regular-expression-syntax).
Within the pattern, you can escape the delimiter with a backslash. For instance:

```
${foo/abc\/def/abc.def/}
```

However, it's usually easier and more readable just to use the alternate
delimiter:

```
${foo|abc/def|abc.def|}
```

**`replacement`**

`replacement` is the replacement string. Within this string:

* You can escape the delimiter with a leading backslash (though, as with
  `regex`, it's usually more readable to use the alternate delimiter).
* You can refer to regular expression groups as "$1", "$2", etc.
* You can escape a literal dollar sign with a backslash.
* Simple variable substitutions (`$var`, `${var}`, `${var[0]}`, etc.) are
  permitted the replacement. Ternary IFs and nested inline editing are _not_ 
  supported. 

**`flags`**  

Two optional flags are supported:

* `i` - do case-blind matching
* `g` - substitute all matches, not just the first one

To specify both, just use `gi` or `ig`.

**Examples**

Assume the following variables:

```
foo: Hello
filename: 01-Why-Spark.py
basename: 01-Why-Spark
```

* `${filename/\d/X/}` yields "X1-Why-Spark.py"
* `${filename/\d/X/g}` yields "XX-Why-Spark.py"
* `${basename/(\d+)(-.*)$/$1s$2/` yields "01s-Why-Spark"
* `${filename/\.py//}` yields "01-Why-Spark"

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

Or, if you want to use a different `databricks` authentication profile than
`DEFAULT`:

`bdc --upload --dprofile profile shard-path [build-yaml]`

`--dbprofile` (or `-P`) corresponds _directly_ to the `databricks`
command's `--profile` argument.

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

**Uploads and build profiles**: If two notebooks with separate profiles
("amazon" and "azure") map to the same `dest` value, `bdc` would overwrite one
of them during the upload and would arbitrarily choose one on the download.
Now, it adds an "az" or "am" qualifier to the uploaded file. For instance,
assume `build.yaml` has these two notebooks (and assume typical values in
`notebook_defaults`):
  
```
  - src: 02-ETL-Process-Overview-az.py
    dest: ${target_lang}/02-ETL-Process-Overview.py
    only_in_profile: azure

  - src: 02-ETL-Process-Overview-am.py
    dest: ${target_lang}/02-ETL-Process-Overview.py
    only_in_profile: amazon
```  

Both notebooks map to the same build destination. `bdc --upload` will upload
`02-ETL-Process-Overview-az.py` as `01-az-ETL-Process-Overview.py`, and it will
upload `02-ETL-Process-Overview-am.py` as `01-am-ETL-Process-Overview.py`.

`bdc` always applies the `am` or `az` prefix, if `only_in_profile` is specified,
even if there are no destination conflicts. The prefix is placed _after_ any
numerals in the destination file name; if there are no numerals, it's placed
at the beginning.

#### Prerequisite
 
This option _requires_ the `databricks-cli` package, which is only
supported on Python 2. You _must_ install and configure the `databricks-cli`
package. The shard to which the notebooks are uploaded is part of the
`databricks-cli` configuration.

See <https://docs.databricks.com/user-guide/databricks-cli.html> for details.

### Download the course's notebooks to a Databricks shard

You can use `bdc` to download all notebooks for a course to a Databricks shard.

`bdc --download shard-path [build-yaml]`

Or, if you want to use a different `databricks` authentication profile than
`DEFAULT`:

`bdc --download --dprofile profile shard-path [build-yaml]`

`--dbprofile` (or `-P`) corresponds _directly_ to the `databricks`
command's `--profile` argument.

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

[build.yaml]: build.yaml
