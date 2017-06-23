# Change Log for BDC

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
