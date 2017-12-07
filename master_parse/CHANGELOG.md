# Change Log for Master Parse Tool

Version 1.11.1:

* Master parser now emits `%scala`, `%python`, `%r`, `%sql`, `%markdown` 
  and `%markdown-sandbox` on their own lines (i.e., any cell content starts
  on the second line of the cell). Previously, it only did so for `%scala`,
  `%python` and `%r`. With other "magic" cells (`%run`, `%fs`, `%sh`), the
  cell content starts on the same line as the magic token.
* Changed insertion of Creative Commons license (`-cc` option) to ensure that
  the license cell is `%md-markdown`, not `%md`.
* Fixed incorrect formatting when both the Databricks training heading and the
  Creative Commons license are selected.

Version 1.11.0:

* Fixed footer logic to handle Scala (i.e., to use the proper language-specific)
  comment syntax.
* Added `--notebook-footer` and `--footer` arguments to control the generated
  footer (both the content and whether the footer is added). Consistent with
  `--notebook-heading` and `--heading`, the footer is off by default.
* Added `--copyright YEAR` option, to specify the copyright year that is
  substituted into the default footer.

Version 1.10.0:

* Added automatic copyright footer to generated notebooks.

Version 1.9.0:

* Video tag is now `-- VIDEO id [title]`, where `id` is a video ID. Videos
  are now assumed to reside on Wistia.com.
* `:HINT:` now expands to an image and text, not just text.
* `:NOTE:` has been removed. (Use `:SIDENOTE:`, instead.)
* `:KEYPOINT:`, `:INSIGHT:`, `:WARNING` have been removed.
* Fixed code that renders inline tokens (`:HINT:`, etc.) to render them in
  `%md-sandbox` if necessary.

Version 1.8.0

* Added support for inline callouts. The tokens `:HINT:`, `:CAUTION:`, 
  `:WARNING:`,`:BESTPRACTICE:`, `:KEYPOINT:`, `:SIDENOTE:`, and `:INSIGHT:`
  are replaced, inline, with appropriate expansions.

Version 1.7.2:

* Fixes to handle both `%r` and `%md-sandbox`.

Version 1.7.1:

* Updates to fix handling of `%run`. **Breaks `%r`!**

Version 1.7.0:

* Add cell validity checks that ensure that some commands can only appear
  in certain cells.
* `TEST` cells can now have an annotation after the word `TEST`, and if
  the annotation is missing, the tool adds one. Thus, in a code cell,
  the line `TEST - You can use this cell to test your solution` will be
  emitted as is, but the cell `TEST` will be transformed to
  `TEST - Run this cell to test your solution`. 
  
Version 1.6.0:

* Removed `NOTEBOOK_HEADING` command, in favor of `--heading` command
  line option that automatically adds the heading as the first cell in
  generated notebooks.

Version 1.5.0:

* Added support for `VIDEO <url> <title>` command.
* Updated format of default notebook heading.
* Deprecated the `DATABRICKS_ONLY` command.
* Un-deprecated the `PRIVATE_TEST` command.

Version 1.4.1:

* Fixed bug where notebook heading wasn't properly generated.
* Changed `TRAINING_HEADING` to the more general-purpose `NOTEBOOK_HEADING`.
* Changed `-th` (`--training-heading`) option to `-nh` (`--notebook-heading`),
  and made corresponding API changes.

Version 1.4.0:

* Added `TRAINING_HEADING` command, which replaces the (Markdown) cell in
  which it appears with a standard heading.
* Added a `-th` (`--training-heading`) command line option that permits
  overriding the standard heading with the contents of some other file.

Version 1.3.1:

* Fixed a bug causing a mishandling of any language cell (e.g., `%sql`, `%r`)
  that has the `ALL_NOTEBOOKS` _and_ one of `TODO` or `ANSWER`.

Version 1.3.0:

* Master parser now generates _three_ broad kinds of notebooks: instructor, 
  exercises, and answers. 
    - The _exercises_ notebook is what used to be called the "student" notebook.
      It omits any cells marked `ANSWER`, and it omits any `INSTRUCTOR_NOTE`
      cells.
    - The _instructor_ notebook is what used to be called the "answers" notebook.
      It omits any `TODO` cells, contains all `ANSWER` cells, and contains
      reformatted `INSTRUCTOR_NOTE` cells.
    - The _answers_ notebook is almost identical to the _instructor_ notebook,
      except that it does not contain `INSTRUCTOR_NOTE` cells.
* Added deprecation warnings for `PRIVATE_TEST`, `INLINE` and 
  `IPYTHON_ONLY` labels.
* Added change log.
