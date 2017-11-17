# Change Log for BDC

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
