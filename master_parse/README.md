# Master Parse Tool

## Introduction

The master parse tool parses Databricks notebooks (in source form) and,
based on metadata embedded within the notebooks, produces (possibly multiple)
output notebooks.

It can be used as a command or as a library.

The tool is usable from either Python 2 or Python 3.

## Installation

To install, run

```
python setup.py install
```

The setup file installs all required packages, as well as `master_parse`.

## Command line use

Once installed, the master parse tool can be invoked as `master_parse`.
It takes arguments in several groups, and at least one argument from
each group is required.

### Notebook type group

* `-db` or `--databricks`: Generate Databricks notebook(s)
* `-ip` or `--ipython`: Generate IPython (i.e., Jupyter) notebook(s)

More than one option may be specified.

### Notebook language group

* `-sc` or `--scala`: Generate Scala notebooks
* `-py` or `--python`: Generate Python notebooks
* `-r` or `--rproject`: Generate R notebooks
* `-sq` or `--sql`: Generate SQL notebooks

More than one option may be specified.

### Target audience group

* `-in` or `--instructor`: Generate instructor notebooks (notebooks ending
  with `_instructor`). Instructor notebooks contain all instructor note cells
  and all answer cells. Exercise cells (those marked `TODO`) are omitted.

* `-an` or `--answers`: Generate answer notebooks (notebooks ending
  with `_answers`). Answer notebooks contain all answer cells. Exercise cells 
  (those marked `TODO`) are omitted, as are instructor note cells. Thus, an
  answer notebook is the same as the corresponding notebook _minus_ the 
  instructor notes.

* `-ex` or `--exercises`: Generate exercise notebooks (notebooks with 
  `_exercises`). These notebooks are the primary student notebooks. They omit
  answer cells and instructor notes and contain all cells marked `TODO`.

More than one option may be specified.

### Miscellaneous options

* `-cc`: Add a Markdown cell at the top of the notebook that identifies the 
  notebook as being released under a Creative Commons
  [Attribution-NonCommercial-NoDerivatives 4.0 International](https://creativecommons.org/licenses/by-nc-nd/4.0/) 
  (CC BY-NC-ND 4.0) license.
* `-d OUTPUT_DIR`: Specify the output directory for the build artifacts. 
  Defaults to `build_mp`
* `-ei ENCODING`: Specifies the encoding of the input file. Defaults to
  "cp1252", though a more useful default might be "UTF-8".
* `-eo ENCODING`: Specifies the desired encoding of the output files.
  Defaults to "UTF-8".
* `-nh PATH` or `--notebook-heading PATH`: Specifies the path to a file
  containing Markdown and/or HTML to be used as the top-of-notebook heading.
  If not specified, internally coded default HTML is used.
* `--heading`: By default, even if you specify `-nh`, the `master_parse`
  tool does _not_ add the notebook heading at the top of the generated
  notebooks. You need to specify `--heading` to force that behavior.
  (This preserves historical behavior better.)

### Filename group

* `<filename>` specifies the notebook file to parse.
* `-v` or `--version` tells `master_parse` to display its version and exit.
  This option is mutually exclusive with `<filename>`.


## Library use

```python
import master_parse
master_parse.process_notebooks(args)
```

The arguments correspond to the command line parameters. See the source for
details.

## Notebook metadata

The tool looks for various labels, as well as language-specific tokens, within
notebook cells.

### Language tokens

By default, the master parse tool processes `%scala`, `%python`, `%r` and
`%sql` cells specially. How it handles those cells is best described by
example.

Suppose you've run the tool on a Python notebook (i.e., a file ending in `.py`),
and the notebook also contains some `%scala` and `%r` cells.

* If you've specified `--scala` (on the command line) or passed
  `scala=True` (to `master_parse.process_notebooks()`), then the tool will
  create Scala notebooks that contain all non-code cells (Markdown cells,
  `%fs` and `%sh` cells, etc.) in the original, as well as any `%scala` cells.
  All other language code cells will be stripped from the Scala notebooks.
* If you've specified `--rproject` (on the command line) or passed
  `r=True` (to `master_parse.process_notebooks()`), then the tool will
  create R notebooks that contain all non-code cells (Markdown cells,
  `%fs` and `%sh` cells, etc.) in the original, as well as any `%r` cells.
  All other language code cells will be stripped from the R notebooks.
* If you've specified `--python` (on the command line) or passed
  `python=True` (to `master_parse.process_notebooks()`), then the tool will
  create Python notebooks that contain all non-code cells (Markdown cells,
  `%fs` and `%sh` cells, etc.) in the original, as well as any Python
  cells. Since the file ends in `.py`, Python cells are assumed to be
  cells with explicit `%python` magic or any non-decorated (i.e., normal)
  code cells.

You can modify this behavior somewhat, using the labels below.

### Master parse labels

Master parse labels are cells that are marked with special tokens that only
the master parse tool recognizes. Some labels make sense only in code cells.
Others can be used in code cells, Markdown cells, etc.

All  labels _must_ be preceded by a single command character, and the comment
character must be correct for the notebook type. That is, a Python notebook
(ending in `.py`) always uses "#" as the comment character. This is true
even in Markdown cells.

Cells not marked with any label appear in _all_ outputs.

#### Examples

In a Scala code cell:

```scala
// ANSWER
// Scala answer goes here
```

In a markdown cell in a Python notebook:

```
%md
# SCALA_ONLY
This Markdown cell is in a Python notebook, but it only appears in Scala
notebooks generated by the master parse tool.
```

In a Python code cell:

```python
# ANSWER
# Python answer goes here
```

In a Python code cell, this is not valid Master Parse Tool syntax and will simply be a comment:

```python
## ANSWER
# WRONG!
```

#### Valid labels

The valid labels are:

**IPYTHON\_ONLY**

**This cell type is _deprecated_ and will be removed in a future release of
this tool. Use of it will generate warnings.**

Cells which need to be in IPython (or Jupyter) notebooks only.
If IPython notebooks aren't being generated, these cells are stripped out.

**DATABRICKS\_ONLY**

**This cell type is _deprecated_ and will be removed in a future release of
this tool. Use of it will generate warnings.**

Cells which need to be in Databricks notebooks only.

**SCALA\_ONLY**, **PYTHON\_ONLY**, **SQL\_ONLY**, **R\_ONLY**

Cells marked with this show up only when generating notebooks for _lang. These
are for special cells (like Markdown cells, `%fs` cells, `%sh` cells) that you
want to include on a language-dependent basis. For example, if a Markdown cell
is different for Scala vs. Python, then you can create two `%md` cells, with
one marked PYTHON_ONLY and the other marked SCALA_ONLY.

**TODO**

Cells show up only in exercise notebooks. These cells are usually
exercises the user needs to complete.

**ANSWER**

Cells show up only in instructor and answer notebooks.

**TEST**

These cells identify tests and usually follow an exercise cell. Test cells
provide a means for a student to test the solution to an exercise. You can
include an annotation after the word `TEST`. For example:

```
# TEST - Please run this cell to test your solution.
```

If you don't supply an annotation, the tool will add one. So, this line:

```
# TEST
```

will be emitted, in the generated notebooks, as:

```
# TEST - Run this cell to test your solution.
```


**PRIVATE\_TEST**

Cells show up in instructor/answer notebooks.

**VIDEO**

Valid only in Markdown cells, this command is replaced with HTML for a
large video button. When clicked, the button launches a new tab to the
specified URL. The command takes the form `VIDEO url [title]`. `url`
is the link to the video. The title (optional) is the video's title which,
if present, will appear in the button. If no title is supplied, the button
will not contain a title.

**INSTRUCTOR_NOTE**

Valid only in Markdown cells, this command causes the cell to be copied into
the answer, or instructor, notebook and omitted from the student notebook.
An "Instructor Note" header will automatically be added to the cell.

**ALL_NOTEBOOKS**

The cell should be copied into all generated notebooks, regardless of language.
Consider the following code in a Scala notebook:

```
%python
# ALL_NOTEBOOKS
x = 10
```

If you run the master parse tool to create Scala and Python notebooks, with
instructor and student notebooks, that cell will appear in the generated Scala
notebooks (instructor _and_ answers) as well in the generated Python notebooks
(instructor _and_ answers).

**INLINE**

**This cell type is _deprecated_ and will be removed in a future release of
this tool. Use of it will generate warnings.**

Can be used for multilanguage notebooks to force another language
to be inserted. The behavior is a little counterintuitive. Here's an example.

You're processing a notebook called `foo.scala`, so the base language is Scala.
The notebook has these cells somewhere inside:

```
%python
// INLINE
x = 10
```

```
// INLINE
val y = 100
```

The first cell is a Python cell that would _normally_ be suppressed in the
output Scala output; it would either be written to the output Python notebook
or suppressed entirely (if Python output was disabled).

However, because of the `// INLINE`, the cell is written to the output Scala
notebook, instead, and _suppressed_ in the output Python notebook.

Meanwhile, the opposite happens with the second cell. Because the second cell
is Scala, but is marked as `// INLINE`, it is _only_ written to non-Scala
output notebooks.

**NEW_PART**

Start a new part of the lab. A lab can be divided into multiple parts with each
part starting with a cell labeled `NEW_PART`. Every time the tool encounters a `NEW_PART`
label, it creates a new notebook that starts with a cell that runs the _previous_
part notebook (via `%run`), which enables students who are lagging behind to
catch up.

### Master parse inline tokens

The master parser also supports special inline tokens in Markdown cells.
These tokens are replaced with images and, sometimes, markup. The four
currently supported tokens are:

* `:HINT:` A hint for the student.
* `:CAUTION:` A caution or warning
* `:BESTPRACTICE:` Indicates a best practice
* `:SIDENOTE:` Something of note that’s not necessarily 100% pertinent to 
   the rest of the cell.

Here's an example cell containing each token:

```
%md
We're talking about life here, people. This is some important stuff. Pay attention.

:HINT: Don't worry too much.

:CAUTION: Stress'll kill ya, man.

:BESTPRACTICE: Eat right, and get plenty of rest.

:SIDENOTE: No one gets out alive.
```

Currently, these tokens render as follows, in a `%md-sandbox` cell:

![](https://raw.githubusercontent.com/bmc/build-tooling/master/master_parse/images/tokens-rendered.png)
