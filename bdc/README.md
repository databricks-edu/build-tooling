# bdc - the courseware build tool

This directory contains courseware build tool. (_bdc_ stands for
*B*uild *D*atabricks *C*ourse.) It is a single Python program that attempts to
consolidate all aspects of the curriculum build process. It _does_ rely on some
external artifacts. See below for details.

Quick links:

* [Command line usage](#usage)
* [Installation](#installation)
* [Build file syntax](#build-file)

---

## Installation

#### Install the build tools

Once you've activated the appropriate Python virtual environment,
see the [master README](../README.md) for a single command that will install
all the build tools.

---

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

- **`bdc_min_version`** sets the minimum version of `bdc` required to run the
build. Using an older version of `bdc` will cause an automatic build failure.
- **`master_parse_min_version`** sets the minimum version of the master parser
required to run the build. Using an older version of `master_parse` will cause 
an automatic build failure.

The following example says that the `build.yaml` requires at least version
1.21 of `bdc` and version 1.14 of `master_parse`:

```yaml
bdc_min_version: "1.21"
master_parse_min_version: "1.14"
```

### Introduction to variable substitution, plus the `variables` section

Certain `build.yaml` parameters permit _variable substitution_, using the
Python [template string](https://docs.python.org/2.7/library/string.html#template-strings)
syntax. `bdc` supports certain hard-coded variables, as noted in the various
sections, below.

You can also supply your own custom variables, which can be substituted in most
places that support variables. Custom variables are also passed into the
master parser, if [master parsing is enabled](#the-master-subsection).

The variable substitution syntax is powerful. See
[Variable Substitution](#variable-substitution) for complete details.

#### The `variables` section

To define your own variables, just include a `variables` section in your
`build.yaml`. Each field within that section defines a name/value pair,
available for substitution.

For example:

```yaml
variables:
  author: Databricks
  revised: 2018-09-30
```

That section defines two substitutions: `${author}`, which will be replaced
with the string "Databricks", and `${revised}`, which will be replaced with
the string "2018-09-30".

#### Variables and Cell Templates

The [master parser][] allows Markdown cells to be
[processed as templates][cell templates].
Any variables you define in your `variables` section will be passed to the
master parser and will be available for substitution in your Markdown
cells—provided you [enable Markdown cell templates](#enable_templates).

### Course info

The `course_info` section defines information about the course. It contains
the following fields:

- **`name`**: (REQUIRED) The name of the course (e.g., "Databricks-Delta"). The 
  name should not have any white space, as it is used to construct file names.
- **`title`**: (OPTIONAL) A human-readable title for the course, which can
  contain white space (unlike `name`). Default: The value of `name`.
- **`version`**: (REQUIRED) The (semantic) version number of the course (e.g., 
  "1.0.1").
- **`type`**: (REQUIRED) The course type. Legal values are "ilt" (for instructor-led
  materials) and "self-paced".
- **`copyright_year`**: (OPTIONAL) Copyright year of the course materials. Defaults
  to the current year.
- **`class_setup`**: (OPTIONAL) Path to the class setup instructions (for site
  managers of a given training site) on how to prepare the classroom 
  environment. For Databricks classes, a survey exists for this purpose. 
  However, for partners, this document summarizes the minimum needs. The path
  relative to the directory containing _build file_. If defined, this file will 
  be copied to the top of the destination directory or directories. Only
  meaningful for ILT classes.
- **`schedule`**: (OPTIONAL) Path to a document that describes the recommended
  teaching schedule for the class. Only meaningful for ILT classes.
- **`prep`**: (OPTIONAL) Path to a Markdown document that outlines any instructor
  preparation that must be done before teaching the class. The file, if
  specified, is copied to `InstructorFiles/Preparation.md` under the target
  directory. An HTML version is also generated there. Only meaningful for
  ILT classes.
- **`deprecated`**: (OPTIONAL) If present and true, this field marks the course
  as deprecated (i.e., no longer used). Attempts to build the course will
  fail. Default: false  

Example sections:

```yaml
course_info:
  name: Databricks-Delta
  title: Databricks Delta
  version: 1.0.0
  type: self-paced
```

```yaml
course_info:
  name: Spark-ILT
  version: 2.1.2-SNAPSHOT
  type: ilt 
```

### A Note about Documents

`bdc` can copy documents into the build output directory, optionally
generating different kinds of output formats. This section describes
document-related configuration items and sections within the `build.yaml`
file.

#### Markdown, HTML and PDF

`bdc` can process Markdown files, producing both HTML and PDF output. It
can also generate PDF output from HTML files or HTML templates.

When generating HTML and PDF from Markdown, `bdc` uses an internal HTML
stylesheet, by default. However, you can override that stylesheet with
the `markdown` section:

```yaml
markdown:
  html_stylesheet: path/to/my/stylesheet.css
```

If you specify `markdown.html_stylesheet`, the stylesheet you specify is
inserting, inline, in each HTML file that is generated from Markdown source.
Unless absolute, the path is assumed to be relative to the build file.

### Output Generation

Several settings help define the layout of the final built course.

- **`student_dbc`**: (OPTIONAL) The name of the DBC that contains student notebooks.
  Defaults to `Labs.dbc`.
- **`instructor_dbc`**: (OPTIONAL) The name of the DBC that contains instructor
  notebooks. Defaults to `Instructor-Labs.dbc`. Note that this DBC is _only_
  created if at least one instructor notebook is generated. See
  [Notebooks](#notebooks) for details.
- **`student_dir`**: (OPTIONAL) The name of the folder, relative to the top of
  the output directory, in which to store student files such as the generated
  student DBC. If explicitly set to the empty string (''), the student DBC
  will be written to the top-level output directory. This value _must_ not
  be the same as `instructor_dir`. Default: `StudentFiles`.
- **`instructor_dir`**: (OPTIONAL) The name of the folder, relative to the top of
  the output directory, in which to store instructor files such as the generated
  instructor DBC. If explicitly set to the empty string (''), the instructor DBC
  will be written to the top-level output directory. This value _must_ not
  be the same as `student_dir`. Default: `StudentFiles`.
- **`keep_labs_dir`**: (OPTIONAL) While generating output notebooks, the build
  tools stash them in directories within the output directory. For example, if
  the student DBC is called `Labs.dbc`, then the tools will stash the notebooks
  in a `Labs` directory under `student_dir`. The DBC is then generated from that
  directory. If `keep_labs_dir` is `false`, that directory is removed after the
  corresponding DBC is built. If `keep_labs_dir` is `true`, that directory is
  not removed (which can be useful for debugging).

The default values are generally useful for an ILT class, where you want
separate instructor and student areas and DBCs. A typical self-paced class
might use these values:

```yaml
student_dir: ''   # DBC at the top level
student_dbc: Lessons.dbc

# instructor_dir and instructor_dbc are untouched, but the notebooks
# are configured so that no instructor notebooks are generated. Thus, the
# instructor DBC will never be written.
``` 

#### The top-most DBC folder

A DBC file is a special kind of zip file containing JSON-encoded notebooks.
By default, when `bdc` generates the final DBC files, it places all notebooks
under a top-level directory named after the course. You can change that
strategy by setting the **`top_dbc_folder_name`** variable.

The following variables can be substituted into this value:

| Variable            | Meaning
| ------------------- | -------
| `${course_name}`    | the course name, from `course_info.name`
| `${course_version}` | the course version, from `course_info.version`
| `${course_id}`      | convenience variable: same as `${course_name}-${course_version}`
| `${profile}`        | the name of the current build profile ("amazon" or "azure"), if any
| your variables      | any [custom variables you define](#where-do-variables-come-from)

Examples:

```yaml
top_dbc_folder_name: Course-${course_name}-${course_version}
top_dbc_folder_name: Lessons
top_dbc_folder_name: ${course_name}  # same as the default
```

#### Slides

While we don't currently teach from slides, if you have some slides that
accompany your course, you can include those slides via the `slides` section.
`slides` consists of a series of (`src`, `dest` pairs), one for each file to be
copied. The `src` path is relative to the location of the `build.yaml` file.
The `dest` is relative to a `Slides` directory beneath the instructor directory. 
See [Output Generation][#output-generation] for details on the instructor
directory.

Another field, `skip`, can be set to `true` to cause the file to be skipped.
This is an alternative to commenting the section out.

Within the `dest` field, the following [variable substitutions](#variable-substitution)
are available:

| VARIABLE       | DESCRIPTION
| -------------- | -----------
| `${basename}`  | the base file name of the `src`, WITHOUT the extension
| `${filename}`  | the base file name of the `src`, WITH the extension
| `${extension}` | the `src` file's extension

For example:

```yaml
slides:
  -
    src: Slides/Welcome.pptx
    dest: Presentations/00-$filename
  -
    src: Slides/Architecture.pptx
    dest: Presentations/01-$filename
    skip: true
```

In this example, there are two slide decks, a "welcome" deck and an
"architecture" deck. 

The architecture deck is skipped, because `skip` is set to `true`. 

The welcome deck is located at `Slides/Welcome.pptx` below the directory
containing the `build.yaml`. If `instructor_dir` is set to its default file,
that file will be copied to
`<build_output_dir>/InstructorFiles/Slides/Welcome.pptx`.

#### Data sets

It's also possible to include data sets in the output directory. This section
is very similar to the `slides` section. It consists of a series of (`src`,
`dest` pairs), one for each file to be copied. The `src` path is relative to
the location of the `build.yaml` file. The `dest` is relative to a generated
`Datasets` directory under the build output directory.

Another field, `skip`, can be set to `true` to cause the file to be skipped.
This is an alternative to commenting the section out.

Within the `dest` field, the following [variable substitutions](#variable-substitution)
are available:

**WARNING**: The directory that contains each dataset file must also contain
a `LICENSE.md` file that describes the license for the data and a `README.md`
file that briefly describes the data and where it came from. The build will
abort if those files are not present and non-empty.

| VARIABLE       | DESCRIPTION
| -------------- | -----------
| `${basename}`  | the base file name of the `src`, _without_ the extension
| `${filename}`  | the base file name of the `src`, _with_ the extension
| `${extension}` | the `src` file's extension

For example:

```yaml
datasets:
  -
    src: datasets/pets.csv
    dest: pets/$basename
  - 
    src: datasets/autos.csv
    dest: autos/$basename
    skip: true
```

In this example, there are two data sets, `autos.csv` and `pets.csv`,
each of which resides under separate directories within the `datasets` directory
that's right beneath `build.yaml`. 

The `autos.csv` dataset is ignored, because `skip` is set to `true`.

The `pets.csv` dataset is copied to `<build_output>/Datasets/pets/pets.csv`.
Its `LICENSE.md` and `README.md` files are copied to the same directory,
as are their (generated) HTML and PDF counterparts.

#### Miscellaneous files and templates

The `misc_files` section provides the mechanism for copying any other kind of
non-notebook file into the build directory. ([Notebooks](#notebooks) are
handled specially.)

`misc_files` consists of a list of source documents, along with instructions
on how to copy them. Each file section can have the following fields:

**`src`**: (REQUIRED) The path to the source file, relative to the directory
containing `build.yaml`.
  
**`dest`** (REQUIRED) The destination path, relative to the top of the
build output directory (or the profile subdirectory, if
[Build Profiles](#build-profiles) are enabled). A value of "." means
"top-level directory". This parameter can be a file or a directory. If the
destination does not have an extension, it is assumed to be a directory,
unless you set `dest_is_dir` to false.
  
The following substitutions are permitted within `dest`:

| SUBSTITUTION   | DESCRIPTION
| -------------- | -----------
| `${basename}`  | the base file name of the source, _without_ the extension
| `${filename}`  | the base file name of the source, _with_ the extension
| `${extension}` | the file extension
| your variables | Any variables defined in the `variables` section, without prefix. 

**`dest_is_dir`**: (OPTIONAL) `true` indicates that `dest` is intended to
be a directory; `false` indicates that it is a file. Defaults to `false`.
You can't set this to `true` if the destination has an extension.
  
**`template`**: (OPTIONAL) `true` indicates that the source file is actually
a [Mustache][] template, which allows you to use variable substitution and
conditional text based on variables. For a brief overview of Mustache,
see [Basic Mustache Syntax](#basic-mustache-syntax), below.

If the file is not a text file (as determined by its extension), then
`template` cannot be set to `true`.

The following variables are made available to templates:

| SUBSTITUTION        | DESCRIPTION
| ------------------- | -----------
| `course_info.<var>` | Any variable from the `course_info` section. e.g., `{{course_info.name}}`
| `variables.<var>`   | Any variable from the `variables` section. e.g., `{{variables.myVar}}`
| `amazon`            | Set to "Amazon" (which also evaluates as true for conditional template logic) if the current build profile is "amazon". Set to '' (which also evaluates as false for conditional template logic) if the current build profile is not "amazon" or if build profiles are disabled.
| `azure`             | Set to "Azure (which also evaluates as true for conditional template logic) if the current build profile is "amazon". Set to '' (which also evaluates as false for conditional template logic) if the current build profile is not "azure" or if build profiles are disabled.

In addition to template processing, `bdc` performs other processing when
copying miscellaneous files.

- If `src` is an HTML file and `dest` is a directory, the HTML file is copied
  to the destination (after optionally being expanded from a template). Then, 
  a PDF is generated from the HTML and placed in the same `dest` directory.

- If `src` is a Markdown file (that is, it has extension `.md` or `.markdown`)
  and `dest` is a directory, the Markdown file is copied to the destination
  (after optionally being expanded from a template). Then, an HTML version
  is generated and copied to `dest`. Finally, a PDF is generated from the HTML
  and copied to `dest`.


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

### Notebooks

Source notebooks listed in the `build.yaml` are parsed, run through the master
parser, converted into multiple output notebooks, and, ultimately, gathered
into a single Databricks DBC file for easy import.

This section discusses the various notebook-related settings in `build.yaml`.

Note that DBC file generation is discussed in [Output Generation](#output-generation).

#### The `src_base` configuration item

`src_base` defines the root location of the notebooks. Use `.` if the notebook
locations are relative to the directory containing `build.yaml`. Otherwise,
specify the location as a relative path. Each notebook's `src` attribute
will be appended to the value of `src_base` to locate the notebook file.

Examples:

```yaml
src_base: .              # notebooks are under the directory containing the build file
src_base: ../../modules  # notebooks are under the "modules" directory
```

#### The `notebooks` section

The `notebooks` section is a list of notebooks to be processed and included
in the course. Each notebook is parsed and stored in the output DBC file(s).
Optionally, source notebooks can be processed by the [master parser][],
producing multiple output notebooks.

The notebooks are assumed to be in source-export format.

**WARNING**: The notebooks should be encoded in ASCII or UTF-8. Other encodings
(e.g., ISO-8859.1 or CP-1252) might cause the build to abort.

Each notebook in the `notebooks` section can have the following fields.

##### `src`
 
REQUIRED: The path to the notebook, relative to `src_base`.

##### `dest`

REQUIRED: The destination path within the DBC file and within the
student lab directory. (See [Output Generation](#output-generation).) For
notebooks _not_ processed by the master parser, this destination is the path
to which to copy the source notebook.

For notebooks that are to be run through the master parser (see below), the
destination format depends on how many different output languages are being
generated. If the master parser is generate output for just a single target
language (such as Python), the destination should be a directory.

If the master parser is generating output for multiple target languages (e.g., 
Scala _and_ Python), then the pattern _must_ contain the `${target_lang}` 
substitution and should also contain the `${target_extension}` substitution,
to differentiate the destination. 

In short:

- If you specify `${target_lang}` in the dest value, the target master parse
  language is substituted, for each language-generated notebook.
- If you don't specify `${target_lang}`, and there are multiple languages
  selected in the "master" section, you'll get an error.


For example, here's a sample entry for a master-parsed notebook:

```yaml
src: Introduction.py
dest: ${target_lang}/Introduction.${target_extension}
master:
  enabled: true
  scala: true
  python: true
```

Here is one for a non-master parsed notebook (i.e., one that is just copied):

```yaml
src: Introduction.py
dest: $filename
```

(If this seems confusing, just try different variations, set `keep_labs_dir`
to `true`, and examine the output directory after running a build. The behavior
will become clear.)

Within the `dest` field, the following substitutions are always honored:

| VARIABLE       | DESCRIPTION
| -------------- | -----------
| `${basename}`  | the base file name of the `src`, _without_ the extension
| `${filename}`  | the base file name of the `src`, _with_ the extension
| `${extension}` | the `src` file's extension

In addition, if master parsing is enabled for the notebook, the following
substitutions are also permitted: 

| VARIABLE              | DESCRIPTION
| --------------------- | -----------
| `${target_lang}`      | the output notebook's language (e.g, "Scala", "Python", etc.) 
| `${target_extension}` | the output notebook's extension, which may differ from the source extension
| `${notebook_type}`    | the notebook type ("exercises", "answers", "instructor"). Also see [`notebook_type_name`](#notebook-type-name), below.


##### `skip`

OPTIONAL: If set to `true`, the notebook is skipped. Defaults to `false`.
Setting `skip` to `true` is a convenient way to ignore a notebook without
commenting it out. (You can also comment it out, if you prefer.)

##### `upload_download`

OPTIONAL: `true` if this notebook should be uploaded and downloaded with the
`bdc` upload (`--upload`) or download (`--download`) commands are specified.
Defaults to `true`.

Setting this value to `false` is useful (and, often, necessary) if you're
double-processing a notebook for some reason.

##### `only_in_profile`

Mark the notebook as either 'amazon' or 'azure', indicating that it is 
Amazon-only or Azure-only.  If this value is set, the master parser must be 
enabled _and_ `use_profiles` must be `true`. (See [Build Profiles](#build-profiles).)

##### The `master` subsection

The `master` subsection, if present and enabled within a notebook, marks the 
notebook as a master notebook to be run through the [master parser][]. This
section contains the configuration parameters for the master parser, telling it
how to process the notebook.

If the `master` section is missing or disabled, the source notebook is just
copied to the output directory.

The following parameters are supported.

**NOTE**: There's no option to enable or disable generation of exercises
notebooks. Those notebooks are _always_ generated, if master parsing is
enabled.

###### `enabled`

OPTIONAL: `true` to enable master parsing, `false` to disable it. Default:
`false`.

The easiest way to enable master parsing with all the defaults is:

```yaml
master:
  enabled: true
```

###### `answers`

OPTIONAL: `true` to enabled generation of the answers notebooks, `false`
to disable generation of answers notebooks. Default: `true`.

###### `instructor`

OPTIONAL: `true` to enabled generation of the instructor notebooks, `false`
to disable generation of instructor notebooks. Default: `true`.

###### `scala`

OPTIONAL: `true` to enable generation of Scala notebooks, `false`
to disable generation of Scala notebooks. Default: `true`.

###### `python`

OPTIONAL: `true` to enable generation of Python notebooks, `false`
to disable generation of Scala notebooks. Default: `true`.

###### `r`

OPTIONAL: `true` to enable generation of R notebooks, `false`
to disable generation of R notebooks. Default: `false`.

###### `sql`

OPTIONAL: `true` to enable generation of SQL notebooks, `false`
to disable generation of SQL notebooks. Default: `false`.

###### `enable_templates`

OPTIONAL: If `true`, then
[Markdown cells will be processed as templates][cell templates]. Otherwise,
they won't. Default: `false`.

###### `encoding_in`

OPTIONAL: The encoding to use when reading the master notebook. Default: UTF-8.

###### `encoding_out`

OPTIONAL: The encoding to use when writing the output notebooks. Default: UTF-8.

###### `heading`

`heading` is an OPTIONAL subsection that defines whether to generate a notebook
heading cell in each output notebook. Heading supports two fields:

| FIELD     | MEANING
| --------- | -------
| `path`    | Path to a notebook heading file. The path is relative to the build file directory. The file must be HTML or Markdown and is inserted into a `%md-sandbox` cell at the top of each notebook. If not specified, or if set to "DEFAULT", an internal "Databricks Academy" default is used.
| `enabled` | Whether or not to insert the heading. `true` by default. One use case for `false` is to override [notebook defaults](#notebook-defaults) (see below) for a notebook.

Example:

```yaml
src: Foo.scala
dest: ${target_lang}/Foo.${target_extension}
master:
  enabled: true
  heading:
    path: misc_files/heading.md
```

###### `footer`

`footer` is an OPTIONAL subsection that defines whether to generate a notebook
footer cell in each output notebook. Heading supports two fields:

| FIELD     | MEANING
| --------- | -------
| `path`    | Path to a notebook footer file. The path is relative to the build file directory. The file must be HTML or Markdown and is inserted into a `%md-sandbox` cell at the bottom of each notebook. If not specified, or if set to "DEFAULT", an internal default (a copyright cell) is used.
| `enabled` | Whether or not to insert the heading. `true` by default. One use case for `false` is to override [notebook defaults](#notebook-defaults) (see below) for a notebook.

Example:

```yaml
src: Foo.scala
dest: ${target_lang}/Foo.${target_extension}
master:
  enabled: true
  footer:
    path: misc_files/footer.md
```

##### `notebook_type_name`

This section defines the value of the built-in `${notebook_type}` variable.
As the master parser processes a notebook, it can generate three basic types
of notebooks: exercises, answers and instructor notebooks. In some places,
notably `dest` values, you can use`${notebook_type}` to substitute the
current value. For example, consider this `notebook` definition:

```yaml
notebooks:
  -
    src: 01-Intro.py
    dest: $target_lang/01-Intro-$notebook_type.$target_extension
    master:
      enabled: true
```

With that definition, the master parser will create six notebooks:

- A Scala exercises notebook
- A Python exercises notebook
- A Scala answers notebook
- A Python answers notebook
- A Scala instructor notebook
- A Python instructor notebook

As it generates each of those notebooks, it will expand the `dest` pattern
accordingly. It will generate the following output notebooks:

| OUTPUT NOTEBOOK            | GENERATED PARTIAL PATH
| -------------------------- | ----------------------
| Scala exercises notebook   | `Scala/01-Intro-exercises.scala` (in student directory)
| Python exercises notebook  | `Python/01-Intro-exercises.py` (in student directory)
| Scala answers notebook     | `Scala/01-Intro-exercises.scala` (in student directory)
| Python answers notebook    | `Python/01-Intro-exercises.py` (in student directory)
| Scala instructor notebook  | `Scala/01-Intro.scala` (in instructor directory)
| Python instructor notebook | `Python/01-Intro.py` (in instructor directory)

From that example, we can see that the default values for `${notebook_type}`
are:

| NOTEBOOK TYPE  | GENERATED PARTIAL PATH
| -------------- | ----------------------
| exercises      | "exercises"
| answers        | "answers"
| instructor     | ""

The `notebook_type_name` section lets you change one or all of those
values. For instance, suppose we wanted a layout where the exercises notebooks
are at the top level of the labs directory and the answers notebooks
are below them, in a "Solutions" subdirectory. But we still want the
instructor notebooks at the top-level of the instructor labs directory.
We can achieve that by changing our notebook destination and by adjusting
the notebook type names, as shown:

```yaml
notebook_type_name:
  answers: Solutions
  instructor: ''
  exercises: ''

notebooks:
  -
    src: 01-Intro.py
    dest: $target_lang/$notebook_type/01-Intro.$target_extension
    master:
      enabled: true

```


With this change, we'll get the following layout for our generated notebooks:


| OUTPUT NOTEBOOK            | GENERATED PARTIAL PATH
| -------------------------- | ----------------------
| Scala exercises notebook   | `Scala/01-Intro.scala` (in student directory)
| Python exercises notebook  | `Python/01-Intro.py` (in student directory)
| Scala answers notebook     | `Scala/Solutions/01-Intro.scala` (in student directory)
| Python answers notebook    | `Python/Solutions/01-Intro.py` (in student directory)
| Scala instructor notebook  | `Scala/01-Intro.scala` (in instructor directory)
| Python instructor notebook | `Python/01-Intro.py` (in instructor directory)


##### Complete `notebooks` example

Here's an example of a notebooks section:

```yaml
notebooks:
  - src: notebooks/Delta/01-Introduction.py
    dest: '$target_lang/$notebook_type/$notebook_type/$basename.$target_extension'
    master:
      enabled: true
      scala: true
      python: true
      answers: true
      instructor: false

  - src: notebooks/02-Architecture.py
    dest: '$target_lang/$notebook_type/$notebook_type/$basename.$target_extension'
    master:
      enabled: true
      scala: true
      python: true
      answers: true
      instructor: false

  - src: notebooks/03-Tuning.py
    dest: '$target_lang/$notebook_type/$notebook_type/$basename.$target_extension'
    master:
      enabled: true
      scala: true
      python: true
      answers: true
      instructor: false

  - src: notebooks/04-Debugging.py
    dest: '$target_lang/$notebook_type/$notebook_type/$basename.$target_extension'
    master:
      enabled: true
      scala: true
      python: true
      answers: true
      instructor: false

  - src: notebooks/05-Capstone-Project.py
    dest: '$target_lang/$notebook_type/$notebook_type/$basename.$target_extension'
    master:
      enabled: true
      scala: true
      python: true
      answers: true
      instructor: false
```

There's a lot of repetition in that configuration. In the next section, we'll
see how to factor that out.

#### Notebook Defaults

If you find yourself repeating a lot of configuration data in your `notebooks`
section, you can pull the repeated elements out and put them in a special
`notebook_defaults` section. `notebook_defaults` defines default values
for any notebook. You can override those values, if you want, on a
per-notebook basis. `notebook_defaults` can contain default values for
the `master` section, the `heading` section, the `footer` section, and the
`dest` value.

This time, let's start with an example. Let's see how a `notebook_defaults`
section can simplify the
[complete notebooks section example](#complete-notebooks-example),
above.

```yaml
notebook_defaults:
  dest: '$target_lang/$notebook_type/$notebook_type/$basename.$target_extension'
  master:
    enabled: true
    scala: true
    python: true
    answers: true
    instructor: false

notebooks:
  - src: notebooks/Delta/01-Introduction.py

  - src: notebooks/02-Architecture.py

  - src: notebooks/03-Tuning.py

  - src: notebooks/04-Debugging.py

  - src: notebooks/05-Capstone-Project.py
```

Notice how the `dest` and `master` items are now specified once, in the
`notebook_defaults` section, vastly simplifying the list of notebooks.
You can also choose to override the settings, on a per notebook basis.
For example, suppose we want to enable instructor for everything _but_ the
last notebook (the "capstone project"). We can do that by adjusting the
`notebook_defaults` to enable instructor notebooks, then overriding that
default for just the last notebook:

```yaml
notebook_defaults:
  dest: '$target_lang/$notebook_type/$notebook_type/$basename.$target_extension'
  master:
    enabled: true
    scala: true
    python: true
    answers: true
    instructor: true

notebooks:
  - src: notebooks/Delta/01-Introduction.py

  - src: notebooks/02-Architecture.py

  - src: notebooks/03-Tuning.py

  - src: notebooks/04-Debugging.py

  - src: notebooks/05-Capstone-Project.py
    master:
      instructor: false
```

`notebook_defaults` can also contain a `variables` section. For instance:

```yaml
notebook_defaults:
  dest: '$target_lang/$notebook_type/$notebook_type/$basename.$target_extension'
  master:
    enabled: true
    scala: true
    python: true
    answers: true
    instructor: true
  variables:
    suffix: ${notebook_type[0]}
```

Variables defined in `notebook_defaults` are evaluated when each output
notebook is generated and are also passed to the master parser if templates
are enabled. Variables defined here override any variables defined in the
global [`variables`](#the-variables-section) section. However, they cannot
override built-in variables (such as `${notebook_type}` or `${course_id}`).
Any attempt to do so is just ignored.

### Bundles

For some courses (e.g., self-paced), it's useful to be able to generate an
_output bundle_ once the build is complete. `bdc` will do that for you, if you
include a `bundle` section in `build.yaml`.

A _bundle_ is just a zip file containing other files. Currently, a bundle
_cannot_ contain a directory; it can only contain files. (That restriction may
be lifted in the future, if the need arises.)

The `bundle` section consists of a series of (`src`, `dest`) pairs. The `src`
is a file _from the build output directory_ that is to be copied into the
zip file. The `dest` is the name (and, if desired, path) _within_ the zip
file.

If [build profiles](#build-profiles) are being used, `bdc` will generate one
bundle for each profile—that is, one bundle for "amazon" and another bundle
for "azure". If build profiles are not being used, then `bdc` will generate
just one bundle.

Formally, a bundle has the following fields:

**`zipfile`**: (OPTIONAL) The name of the zip file to be generated. This is
not a path; it's a simple file name. It is generated in the top build
directory (if build profiles aren't being used) or in each profile directory
(if build profiles are used).

The following variables are available for substitution within this value:

| VARIABLE            | DESCRIPTION
| ------------------- | -----------
| `${course_name}`    | the name of the course, from `course_info.name`
| `${course_version}` | the course version, from `course_info.version`
| `${profile}`        | the profile ("amazon" or "azure"), or "" if profiles aren't enabled

If `zipfile` is not defined, `bdc` will use `${course_name}-${course_version}.zip`.

**`files`**: The list of (`src`/`dest`) pairs to be zipped up. If empty, then
no bundle is generated. `src` is relative to the top-level build directory (if
build profiles aren't being used) or to the profile directory (if profiles are
being used).

Within `dest`, the following substitutions are permitted:

| VARIABLE       | DESCRIPTION
| -------------- | -----------
| `${basename}`  | the base file name of the `src`, _without_ the extension
| `${filename}`  | the base file name of the `src`, _with_ the extension
| `${extension}` | the `src` file's extension
| `${profile}`   | the profile ("amazon" or "azure"), or "" if profiles aren't enabled
| your variables | variables from the `variables` section.

An example will help clarify this section:

```yaml
bundle:
  zipfile: course.zip
  files:
    -
      src: 00_README.pdf
      dest: $filename
    -
      src: Labs.dbc
      dest: Lessons.dbc
```

In this example, the file `00_README.pdf` will be copied into the zip file
(using the same name), and the `Labs.dbc` file will be copied into the zip
file (but as `Lessons.dbc`). Instead of the default zip file name, `bdc` will
use `course.zip`.

### Variable Substitution

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

### Basic Mustache Syntax

Mustache is a very simple template language. For full details, see
the [Mustache][] manual page. For our purposes, two most useful constructs
are conditional content and variable substitution.

Here's an example of conditional content:

```
{{#amazon}}
Please run this course in Databricks, using the Amazon AWS cloud.
{{/amazon}}
{{#azure}}
Please run this course using Azure Databricks.
{{/azure}}
```

If the variable "amazon" has a non-empty value (or is `true`), then the
first string will be included; otherwise, it'll be suppressed. Likewise, if
the variable "azure" has a non-empty value (or is `true`), then the
second string will be included; otherwise, it'll be suppressed.

This is Mustache's form of an _if_ statement. There is no _else_ statement.
There's a kind of _if not_, however: Simply replace the `#` with a `^`.

```
{{^amazon}}
Rendered if amazon is not defined.
{{/amazon}}
```

This construct also works inline:

```
Mount your {{#amazon}}S3 bucket{{/amazon}}{{#azure}}blob store{{/azure}}
to DBFS.
```

Variable substitution is quite simple: Just enclose the variable's name in
`{{` and `}}`. For example:

```
This is {{course_info.title}}, version {{course_info.version}}
```

If the course title is "A Very Cool Course", and the course version is 1.0.0,
the above string will render as:

```
This is A Very Cool Course, version 1.0.0
```

---

## Usage

Just invoke `bdc` with no arguments for a quick usage message.

`bdc` can be invoke several different ways. Each is described below.

### Getting the abbreviated usage message

Invoke bdc with no arguments to get a quick usage message.

### Getting the full usage message

`bdc -h` or `bdc --help`

### Show only the version

`bdc --version`

### Check your `build.yaml` for errors

Running `bdc --check` against a `build.yaml` file parses the file and
checks it for obvious problems, without actually doing anything else.

`bdc` performs that same validation _automatically_, when you run a
build or use `--upload` or `--download`. But `--check` lets you force
a validation check.

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


[Mustache]: http://mustache.github.io/mustache.5.html
[build.yaml]: build.yaml
[master parser]: ../master_parse/README.md
[cell templates]: ../master_parse/README.md#cells-as-templates
