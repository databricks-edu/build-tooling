# Master Parse Tool

## Introduction

The master parse tool parses Databricks notebooks (in source form) and,
based on metadata embedded within the notebooks, produces (possibly multiple)
output notebooks.

It can be used as a command or as a library.

The tool is usable from either Python 2 or Python 3.

---

## Installation

To install, run

```
python setup.py install
```

The setup file installs all required packages, as well as `master_parse`.

---

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

* `-ct` or `--course-type`: Specifies the course type, ILT ("ilt") or
  Self-paced ("self-paced"). The value of this argument controls how
  the `ILT_ONLY` and `SELF_PACED_ONLY` tags are processed. If not specified,
  "self-paced" is the default.
  
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
* `--templates`: Enable cell templates. See [below](#cells-as-templates)
  for details.
* `-tp PROFILE` or `--target-profile PROFILE`: Target output profile, if any.
  Valid values: amazon, azure
* `--variable <var>`: Supply an initial variable for template substitution.
  Can be used multiple times. `<var>` can be one of:
    - `var=value`: define `var` to substitute the string "value"
    - `var`: define `var` as `True`
    - `!var`: define `var` as `False`

### Filename group

* `<filename>` specifies the notebook file to parse.
* `-v` or `--version` tells `master_parse` to display its version and exit.
  This option is mutually exclusive with `<filename>`.


---

## Library use

```python
import master_parse
master_parse.process_notebooks(args)
```

The arguments correspond to the command line parameters. See the source for
details.

---

## Notebook Processing

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

All labels _must_ be preceded by a comment sequence. For instance:

```
# TODO
// TODO
-- TODO
```

Labels must appear on a line by themselves. Thus, use:

```
%md
// SCALA_ONLY
```

not 

```
%md // SCALA_ONLY
```


#### Unlabeled

Cells not marked with any label are handled specially, depending on the cell
type:

* `%md`, `%md-sandbox`: Markdown cells appear in all output notebooks, unless
  suppressed, for example, with `SCALA_ONLY`, `PYTHON_ONLY`,
  `INSTRUCTOR_NOTE`, etc.
  
* `%fs` and `%sh` cells appear in all output notebooks, unless explicitly
  suppressed.
  
* Code cells only appear in the output notebook for their language, unless
  marked with `ALL_NOTEBOOKS`. Thus, a Scala cell only shows up in Scala 
  notebooks, unless marked with `ALL_NOTEBOOKS`.

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

##### IPYTHON\_ONLY

**This cell type is _deprecated_ and will be removed in a future release of
this tool. Use of it will generate warnings.**

Cells which need to be in IPython (or Jupyter) notebooks only.
If IPython notebooks aren't being generated, these cells are stripped out.

##### DATABRICKS\_ONLY

**This cell type is _deprecated_ and will be removed in a future release of
this tool. Use of it will generate warnings.**

Cells which need to be in Databricks notebooks only.

##### SCALA\_ONLY, PYTHON\_ONLY, SQL\_ONLY, R\_ONLY

Cells marked with this show up only when generating notebooks for _lang_. These
are for special cells (like Markdown cells, `%fs` cells, `%sh` cells) that you
want to include on a language-dependent basis. For example, if a Markdown cell
is different for Scala vs. Python, then you can create two `%md` cells, with
one marked PYTHON_ONLY and the other marked SCALA_ONLY.

##### AMAZON\_ONLY, AZURE\_ONLY

Cells marked with `AMAZON_ONLY` only show up when building for target profile
`amazon`. Cells marked with `AZURE_ONLY` only show up when building for
target profile `azure`.

See the `-tp` command line option (in
[Miscellaneous options](#miscellaneous-options), above) or the 
`bdc` setting `only_in_profile` (in the `bdc`
[Notebooks](../bdc/README.md#notebooks) section).


##### TODO

Cells show up only in exercise notebooks. These cells are usually
exercises the user needs to complete.

As a special case, if the entire TODO cell is comment out, the master parser
will strip the first level of comments. This allows for runnable TODO cells
in source notebooks. Thus, the following three TODO cells are functionally
equivalent in the output notebooks:

Not runnable in source notebook:

```python
# TODO
x = FILL_THIS_IN
```

Runnable in source notebook:

```python
# TODO
#x = FILL_THIS_IN
```

```python
# TODO
# x = FILL_THIS_IN
```

All three cells will render as follows in the Python answers output notebook:

```python
# TODO
x = FILL_THIS_IN
```

**NOTES**:

1. When you create a runnable TODO cell, you can use at most one blank
   character after the leading comment. (The blank is optional.) The master
   parser will remove the leading comment and, optionally, one subsequent
   blank from every commented line _except_ for the line with the "TODO"
   marker.

2. Do **not** precede `TODO` with multiple comment characters, even in a
   runnable `TODO` cell.. It won't work.  That is, use `// TODO` or `# TODO`,
   not `// // TODO` or `# # TODO`. The latter won't be recognized as a
   proper TODO cell.

##### ANSWER

Cells show up only in instructor and answer notebooks.

##### TEST

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


##### PRIVATE\_TEST

Cells show up in instructor/answer notebooks.

##### VIDEO

Valid only in Markdown cells, this command is replaced with HTML for a
large video button. When clicked, the button launches a new tab to the
specified URL. The command takes the form `VIDEO url [title]`. `url`
is the link to the video. The title (optional) is the video's title which,
if present, will appear in the button. If no title is supplied, the button
will not contain a title.

##### INSTRUCTOR_NOTE

Valid only in Markdown cells, this command causes the cell to be copied into
the answer, or instructor, notebook and omitted from the student notebook.
An "Instructor Note" header will automatically be added to the cell.

##### SOURCE_ONLY

Valid in any cell, this tag marks a cell as a source-only cell. Source-only
cells are _never_ copied to output notebooks. Source-only cells are useful 
for many things, such as cells with credentials that are only to be used
during curriculum development.

##### ILT_ONLY

An `ILT_ONLY` cell is only copied to output notebooks if the course type
is "ilt". See the `-ct` (`--content-type`) command line parameter.

##### SELF_PACED_ONLY

An `SELF_PACED_ONLY` cell is only copied to output notebooks if the course type
is "self-paced". See the `-ct` (`--content-type`) command line parameter.

##### ALL_NOTEBOOKS

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

##### INLINE

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

##### NEW_PART

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

![](https://files.training.databricks.com/images/tooling/tokens-rendered.png)

### Cells as templates

The master parser supports treating Markdown cells (`%md` and `%md-sandbox`
cells) as _templates_. This feature is disabled by default, but it can be 
enabled:

- on a per-notebook basis in `build.yaml`, by setting the 
  [`enable_templates`](../bdc/README.md#enable_templates) field in the
  `master` section;
- via the `--templates` command line option, if you're calling the master
  parser from the command line; or
- via a parameter setting to the API, if you're calling the master parser
  programmatically.

When templates are enabled, Markdown cells are treated as 
[Mustache][] templates. Its use, in notebook cells, allows you to:
 
- **do conditional substitution**. For instance, insert this sentence if
  building for Azure, but use this other sentence if building for Amazon.
- **do token substitution**. For instance, substitute the current value of
  this parameter here.
  
See [below](#basic-mustache-syntax) for a brief introduction to Mustache
syntax.

#### Variables you can test or substitute

The master parser defines the following variables automatically:

- `amazon`: Set to "Amazon" (which also evaluates as `true` in a template),
  if building for Amazon. Otherwise, set to an empty string (which also 
  evaluates as `false` in a template).
- `azure`: Set to "Azure" (which also evaluates as `true` in a template),
  if building for Azure. Otherwise, set to an empty string (which also 
  evaluates as `false` in a template).
- `copyright_year`: The value of the copyright year parameter.
- `notebook_language`: The programming language of the notebook being
  generated (e.g., "Scala", "Python", "R", "SQL".)
- `scala`: `true` if the output notebook is Scala, `false` otherwise.
- `python`: `true` if the output notebook is Python, `false` otherwise.
- `r`: `true` if the output notebook is R, `false` otherwise.
- `sql`: `true` if the output notebook is SQL, `false` otherwise.

In addition, you can substitute any variables defined in the `bdc` build file's
[`variables` section](../bdc/README.md#variables-and-cell-templates).

If calling the master parser from the command line, there's a `--variable`
parameter that allows you to pass additional variables.

#### Built-in conditional logic

The Mustache templating also provides some other convenient expansions, each
of which is described here.

##### Incrementally Revealable Hints

The parser supports a special nested block, in Markdown cells only, for
revealable hints. The `{{#HINTS}}` construct introduces a block of hints (and
is closed by `{{/HINTS}}`); such a constructo contains one or more revealable
hints and an optional answer.

This construct is best described by example. Consider the following Markdown
cell:

<pre><code>%md

This is a pithy description of an exercise you are to perform, below.

{{#HINTS}}

{{#HINT}}Revealable hint 1.{{/HINT}}

{{#HINT}}  

Revealable hint 2. Note that the source for this one
is multiple lines _and_ contains some **Markdown** to be
rendered.

{{/HINT}}

{{#ANSWER}}

Still no luck? Here's your answer:

```
df = spark.read.option("inferSchema", "true").option("header", "true").csv("dbfs:/tmp/foo.csv")
df.limit(10).show()
```

{{/ANSWER}}

{{/HINTS}}
</code></pre>


When run through the master parser, the above will render a cell that
initially looks like this:

![](https://files.training.databricks.com/images/tooling/hint-1.png)

After the first button click, the cell will look like this:

![](https://files.training.databricks.com/images/tooling/hint-2.png)

After the second button click, the cell will look like this:

![](https://files.training.databricks.com/images/tooling/hint-3.png)

After the final button click, the cell will look like this:

![](https://files.training.databricks.com/images/tooling/hint-4.png)

**More formally**:

A hints block:

- _must_ contain at least one hint block. A hint is Markdown or HTML in between
  a starting `{{#HINT}}` and an ending `{{/HINT}}`.

- _may_ contain multiple `{{#HINT}}` blocks.

- _may_ contain an `{{#ANSWER}}` block.

`{{#HINTS}}`, `{{#HINT}}` and `{{#ANSWER}}` blocks may contain leading and
trailing blank lines, to aid source readability; those lines are stripped on
output.

#### Basic Mustache Syntax

Mustache is a very simple template language. For full details, see
the [Mustache][] manual page. For our purposes, two most useful constructs
are conditional content and variable substitution.

Here's an example of conditional content:

```
{{#amazon}}
Rendered if amazon is defined.
{{/amazon}}
```

If the variable "amazon" has a non-empty value (or is `true`), then the
string "Rendered if amazon is defined" is included in the cell. Otherwise,
the entire construct is omitted.

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
This is a {{notebook_language}} notebook.
```

If `notebook_language` is set to "Scala", that line will render as:

```
This is a Scala notebook.
```

#### Example

For a more complete example, consider this Markdown cell:

```
%md

In this {{notebook_language}} notebook,
you can access your data by mounting your
{{#amazon}}
S3 bucket
{{/amazon}}
{{#azure}}
Azure blob store
{{/azure}}
to DBFS.
```

When generated with an Amazon profile, in a Scala output notebook, this
cell would become:


```
%md

In this Scala notebook,
you can access your data by mounting your
S3 bucket
to DBFS.
```

[Mustache]: http://mustache.github.io/mustache.5.html
