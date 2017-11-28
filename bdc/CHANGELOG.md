# Change Log for BDC

Version 1.10.0

* `bdc` now generates a version-stamped notebook, with version information,
  at the top level of the generated build, providing an easy way for students
  to determine the course version, even if they rename the folder after import.
* `bdc` no longer includes the version number in the top-level DBC folder.
* A new `bdc_min_version` configuration item is now _required_. It identifies
  the minimum version of `bdc` required to parse a particular `build.yaml`.
  See the sample `build.yaml` for full details.
* Added `variables` section to `build.yaml`, allowing definition of arbitrary
  variables for substitution. See the sample `build.yaml` for details.
* `bdc` now automatically generates a top-level version notebook in the DBC
  files.
* Added a `notebook-defaults` section to capture default notebook settings.
  You can specify default `dest` patterns and the defaults for `master` in
  this new section.
* Added a `$target_extension` substitution, allowing you to substitute the
  post-master parse target file extension into a notebook destination, if
  master parsing is enabled. (The extension is substituted _without_ the 
  leading ".".)  
* Added a `$notebook_type` substitution, allowing you to substitute the
  type of the notebook (answers, exercises or instructor) into the notebook
  destination, if master parsing is enabled.
* Added an option `notebook_type_name` section that allows you to define
  alternate strings for the `$notebook_type` substitution. See the sample
  `build.yaml` for details.
* Changed the substitution of `$extension` so that it does _not_ include
  the leading ".".  
* Added a `master.instructor` setting, allowing you to control whether or not
  instructor notebooks are generated. It's true, by default.
* The target master parse language is _no longer_ automatically inserted.
  If you enable master parsing, and you specify more than one language, you
  _must_ use an explicit substitution of `$target_lang` in the notebook
  destination; otherwise, `bdc` will abort. If you only have a single language,
  you can omit `$target_lang`. 
* Removed the use of a leading "/" in a notebook destination as a means to 
  suppress the automatic insertion of the target language.
* Moved some general-purpose functions into separate `bdcutil` module.

Version 1.9.0:

* The master configuration file (`bdc.cfg`) is no longer used. `bdc` locates
  `gendbc` via the path, and it allows specification of the output directory
  via a new `-d` (or `--dest`) option.
* Updated documentation in the README.

Version 1.8.0:

* Added ability to upload and download entire course via `databricks`
  CLI.
* The master configuration file argument is now optional and defaults to
  `~/.bdc.cfg`. Specify an alternate master configuration file with the
  `-c` option.
* Relative directory names as destinations in `build.yaml` (e.g.,
  `dest: '..'`) are no longer supported. If you want to suppress the
  insertion of a target language, use a destination path that starts with
  "/".
  
Version 1.7.0:

* Added `--list-notebooks` option, providing a quick way to get a listing
  of all the notebooks in a course.

Version 1.6.0:

* Changed to support notebook heading changes in master parser.
  Notebook heading is automatically added by the build tool, unless
  the `notebook_heading.enabled` parameter is set to `false`.

Version 1.5.0:

* Updated to support `notebook_heading` override parameter in the
  `master` section for a notebook. This parameter, if defined, must
  point to a file containing Markdown and/or HTML, to be used to
  replace cells with the `NOTEBOOK_HEADING` command. It corresponds to
  the `--notebook-heading` master parse command-line parameter, and it's
  optional.

Version 1.4.1:

* Emit tool name (bdc) as prefix on verbose messages. 
* When -v is specified, invoke master parser with new _verbose_ argument.

Version 1.4.0:

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
