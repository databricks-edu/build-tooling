# Change Log for BDC

### Version 1.26.1

- Now uses `namedtuple._replace` to copy a `namedtuple` while replacing one
  value, instead of custom code.

### Version 1.27.0

- `gendbc` is now written in Python. Changed `bdc` to call it as a Python
  function, instead of invoking the JVM to run the old command line Scala
  version.
- Refactored `bdc` so that its functionality is available as a library, as
  well as from the command line.

### Version 1.26.0

- `bdc --upload` and `bdc --download` now support multiple instances of a 
  source file. The source file will be uploaded to all the target places.
  Upon download, only the first instance will be downloaded. **Use with care!**
- The build file is now validated before a build, upload, or download is run.   
- Added `--check` (`-C`) argument that can be used to validate a build file
  without running a build.
- `markdown.html_stylesheet` path is now assumed to be relative to the build
  file, unless it's absolute (which isn't recommended).

### Version 1.25.0

- In `misc_files`, if the destination does not have an extension, it is now
  assumed to be a directory, and `dest_is_dir` is inferred to be true.
  You can force it to be false, if need be, but only if the destination
  doesn't have an extension.

### Version 1.24.1

- Fixed a misleading error message when `misc_files` specifies a target
  destination of directory, but `dest_is_dir` isn't set.

### Version 1.24.0

- The `zipfile` and `dest` in the `bundle` section can now substitute the
  current output profile ("amazon" or "azure").

### Version 1.23.2

- Fixed handling of `DB_SHARD_HOME` to ensure that the environment variable
  actually has a non-empty value, not just that it is present.

### Version 1.23.1

- Fixed to pass `notebook_defaults.variables` variables into the master
  parser, making them available to Markdown cell templates.
  
### Version 1.23.0

- Fixed a (newly introduced) bug that caused an abort when copying instructor
  notes.
- `misc_files` templates are now Mustache templates, not Python string templates.
- Instructor notes and guides are now converted to HTML and PDF, where
  appropriate, just like other docs. 

### Version 1.22.0

- Added ability for files in `misc_files` section to be templates, with
  variables substituted in them. See the sample `build.yaml` for details.
- Added ability to generate PDF from a Markdown or HTML miscellaneous file.
- Added a `bundle` section, allowing a zip file of built materials to be
  generated automatically. See the sample `build.yaml` for details.
- The `master` (for a notebook or in `notebook_defaults`) now supports
  an `enable_templates` flag. If set to `true`, Markdown cells in the
  notebook are treated as [Mustache](http://mustache.github.io/mustache.5.html)
  templates by the master parser. (The flag is `false` by default.)
- It is now possible to specify the name of the student DBC, via a new
  `student_dbc` build parameter; it defaults to `Labs.dbc`.
- Similarly, it is now possible to specify the name of the student DBC, via a
  new `instructor_dbc` build parameter; it defaults to `Instructor-Labs.dbc`.
- Added some parse-time validation of the source files (and required `README.md`
  and `LICENSE.md`) for the `datasets` section.
- The `README.md` and `LICENSE.md` files for each data set are also converted
  to HTML and PDF and copied.  
- HTML generated from Markdown now gets anchor links for each generated HTML
  header.
- `course_info` now supports a `title` attribute.

### Version 1.21.0

- Added `course_info.type` build setting, which can be `ilt` or `self-paced`.
  This `build.yaml` setting is now required.

### Version 1.20.0

- Added `--info` and `--shell` command line parameters.

### Version 1.19.0

- Added ability to specify `debug: true` in a `master` section to enable
  master parse-level debug messages for individual notebooks. 

### Version 1.18.2

Fixed bug relating to upload and download capability: If two notebooks
with separate profiles ("amazon" and "azure") map to the same `dest` value,
`bdc` would overwrite one of them during the upload and would arbitrarily
choose one on the download. Now, it adds an "az" or "am" qualifier to the
uploaded file. For instance, assume `build.yaml` has these two notebooks (and
assume typical values in `notebook_defaults`):
  
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

### Version 1.18.1

* Fixed bug: `databricks` command profile wasn't being passed all the places
  it should've been.
  
### Version 1.18.0

* `--upload` and `--download` now honor a `--dbprofile` option to specify
  the authentication profile to use with the `databricks-cli`. This option
  corresponds directly to the `--profile` argument to the `databricks` command.

### Version 1.17.0

* Added support for Amazon and Azure target profiles.

### Version 1.16.0

* Variables can now be defined in the `notebook_defaults` section and in the
  individual notebooks. These variables are expanded at notebook processing
  time, so they can access variables like `${notebook_type}` and
  `${target_lang}`. They can also override variables in the build-wide
  "variables" section.

### Version 1.15.0

* The ternary IF variable substitution syntax now supports simple variable
  substitutions within the comparison string, the "true" string, and the
  "false" string. Double quotes are still required, and only simple 
  substitutions are permitted (i.e., ternary IFs and replacements are not).
  Examples:

```
${foo == "$bar" ? "It matches $$bar." : "It's $foo, not $bar"}
         ^    ^   ^                 ^   ^                   ^
         Note that the double quotes are REQUIRED

${x == "abc${foo}def" ? "YES" : "NO."}

${x == "01-abc" ? "${bar[0]}" : "${bar[-1]}"}
```  

* Similarly, the replacement string in a substitution edit can contain
  simple variable substitutions (but not ternary IFs and replacements).
  Examples:
  
```
${file/^\d+/$x/g}
${foo/\d/ABC${bar[0]}DEF/g}
```

* Variables can now be subscripted, Python-style, as long as they use the
  brace (`${var}`) syntax. Examples: `${foo[0]}`, `${foo[-1]}`,
  `${foo[2:3]}`, `${foo[:]}`, `${foo[:-1]}`, `${foo[1:]}`

* Character escaping changes:
    - To escape a `$`, use `\$` _or_ `$$`.
    - To escape a double quote, use `\"`.

* Fixed a bug: Escaped "$" (i.e., "$$") sequences weren't properly being
  unescaped.

### Version 1.14.0

* Variable substitution now supports a simple inline variable edit capability.
  General format: `${var/regex/replacement/flags}` where `regex` is a
  regular expression, `replacement` is a replacement string, and `flags`
  can be `i` (case-insensitive), `g` (substitute all occurrences, not just
  the first), or `ig` (both). The delimiter can be either "/" or "|", and
  the delimiter can be escaped with a backslash, if necessary. Examples:
  Regular expression groups can be substituted using `$1`, `$2`, etc.

```
# Replace all occurrences of "letters/numbers" with "FOOBAR"
${foo|[a-z]+/\d+|FOOBAR|g}
```

### Version 1.13.0

* Variable substitution now supports a C-like ternary `if` syntax. For instance:

```
${variable == "foo" ? "Got foo" : "No foo"}
```

* Added doctests to `bdc/bdcutil.py`. Just run the module to run the tests.

### Version 1.12.2

* Revised default Version-x.x.x file, removing an excess new line.

### Version 1.12.1

* Fixed upload and download capabilities to handle new (nonexistent) notebooks
  better.

### Version 1.12.0

* Added `top_dbc_folder_name` to `build.yaml`, allowing specification of the
  topmost folder in the generated DBC. Defaults to the course name. See
  the sample `build.yaml` for full details.
* `--upload` and `--download` now support relative shard paths, but only if
  either environment variable "DB_SHARD_HOME" is set or `~/.databrickscfg`
  has a `home` setting in the `DEFAULT` section. See the README for details.

### Version 1.11.0

* Added ability to enable or disable a footer that is automatically added to
  each generated notebook. The feature is controlled by a per-notebook
  `footer` option in the ". (See the sample `build.yaml`). The feature is on by
  default, and the default footer is a Databricks copyright.
* You can now set `master.heading.path` and `master.footer.path` to the
  string "DEFAULT" to force the internal default to be used, which is useful
  if overriding a non-default value in the `notebook_defaults` setting.
* Added `course_info.copyright_year` configuration item, to set the copyright 
  year. Defaults to current year.
* Added `master_parse_min_version`, which is required for any course that
  uses the master parser.

### Version 1.10.1

* Fixed `--upload` and `--download`, which broke due to all the changes in
  1.10.0.
* Added Python 2 check. (Python 3 is no longer supported.)

### Version 1.10.0

* `bdc` now generates a version-stamped notebook, with version information,
  at the top level of the generated build, providing an easy way for students
  to determine the course version, even if they rename the folder after import.
* `bdc` no longer includes the version number in the top-level DBC folder.
* A new `bdc_min_version` configuration item is now _required_. It identifies
  the minimum version of `bdc` required to parse a particular `build.yaml`.
  See the sample `build.yaml` for full details.
* The student and instructor subdirectories (in the DBC) can now be configured
  by `student_dir` and `instructor_dir`, respectively. If not specified, they
  default to `student_dir=StudentFile` and `instructor_dir=InstructorFiles`.
* Added `variables` section to `build.yaml`, allowing definition of arbitrary
  variables for substitution. See the sample `build.yaml` for details.
* `bdc` now automatically generates a top-level version notebook in the DBC
  files.
* Added a `notebook_defaults` section to capture default notebook settings.
  You can specify default `dest` patterns and the defaults for `master` in
  this new section.
* Added a `$target_extension` substitution, allowing you to substitute the
  post-master parse target file extension into a notebook destination, if
  master parsing is enabled. (The extension is substituted _without_ the 
  leading ".".)  
* Added a `$notebook_type` substitution, allowing you to substitute the
  type of the notebook (answers, exercises or instructor) into the notebook
  destination, if master parsing is enabled.
* Added an optional `notebook_type_name` section that allows you to define
  alternate strings for the `$notebook_type` substitution. See the sample
  `build.yaml` for details.
* Changed the substitution of `$extension` so that it does _not_ include
  the leading ".".  
* Added `master.instructor`, `master.answers` and `master.exercises` settings,
  allowing control over whether or not to generate instructor, answer and
  exercises notebooks for a given source notebook. All are true, by default.
* Removed the top-level `notebook_heading` configuration item. The notebook
  heading (both path and the enabled/disabled setting) can now be specified 
  on a per-notebook basis. Defaults can be set in the new `notebook_defaults`
  section. See the sample `build.yaml` for full details.
* The target master parse language is _no longer_ automatically inserted.
  If you enable master parsing, and you specify more than one language, you
  _must_ use an explicit substitution of `$target_lang` in the notebook
  destination; otherwise, `bdc` will abort. If you only have a single language,
  you can omit `$target_lang`. 
* Removed the use of a leading "/" in a notebook destination as a means to 
  suppress the automatic insertion of the target language.
* Moved some general-purpose functions into separate `bdcutil` module.

### Version 1.9.0

* The master configuration file (`bdc.cfg`) is no longer used. `bdc` locates
  `gendbc` via the path, and it allows specification of the output directory
  via a new `-d` (or `--dest`) option.
* Updated documentation in the README.

### Version 1.8.0

* Added ability to upload and download entire course via `databricks`
  CLI.
* The master configuration file argument is now optional and defaults to
  `~/.bdc.cfg`. Specify an alternate master configuration file with the
  `-c` option.
* Relative directory names as destinations in `build.yaml` (e.g.,
  `dest: '..'`) are no longer supported. If you want to suppress the
  insertion of a target language, use a destination path that starts with
  "/".

### Version 1.7.0

* Added `--list-notebooks` option, providing a quick way to get a listing
  of all the notebooks in a course.

### Version 1.6.0

* Changed to support notebook heading changes in master parser.
  Notebook heading is automatically added by the build tool, unless
  the `notebook_heading.enabled` parameter is set to `false`.

### Version 1.5.0

* Updated to support `notebook_heading` override parameter in the
  `master` section for a notebook. This parameter, if defined, must
  point to a file containing Markdown and/or HTML, to be used to
  replace cells with the `NOTEBOOK_HEADING` command. It corresponds to
  the `--notebook-heading` master parse command-line parameter, and it's
  optional.

### Version 1.4.1

* Emit tool name (bdc) as prefix on verbose messages. 
* When -v is specified, invoke master parser with new _verbose_ argument.

### Version 1.4.0

* Updated to work with newest version of master parser, which produces
  three kinds of notebooks (instructor, exercises, answers).
* Updated to copy exercises and answers notebooks to the student labs section,
  and the instructor notebooks to the instructor labs section.
* Removed `student` and `answers` keywords from course configuration `master`
  section. All notebook types are now generated unconditionally. 
* Fixed handling of destination directories.
* Allow use of `${target_lang}` in master parse destination configuration
  (`dest` keyword).
* Added `skip` keyword, allowing files to be "commented out" easily.
* Added change log.
