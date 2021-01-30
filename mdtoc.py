#!/usr/bin/env python

"""
Quick and dirty Python script to generate a (Markdown) table of contents
from a Markdown source file.

- Only supports the "# header", "## header", etc., style of Markdown header.
- The first "#" for a header must be in column 0.
- Skips any header with the text "Table of Contents" (regardless of case)
- Ignores fenced code blocks.
- Writes the table of contents to standard output.

You're responsible for copying and pasting the new table of contents into
the source Markdown document (for now).
"""

import sys
import os
import codecs
import re

if sys.version_info[0:2] < (3, 7):
    sys.stderr.write("Requires Python 3.\n")
    sys.exit(1)

if len(sys.argv) == 2:
    max_level = 6
    path = sys.argv[1]
elif len(sys.argv) == 3:
    max_level = int(sys.argv[2])
    path = sys.argv[1]
else:
    print(
        f"Usage: {os.path.basename(sys.argv[0])} markdown [maxlevel]", file=sys.stderr
    )
    sys.exit(1)

in_fenced_block = False
header_re = re.compile(r"^(#+)\s*(.*)\s*$")
for line in codecs.open(sys.argv[1], mode="r", encoding="utf-8").readlines():
    if len(line.strip()) == 0:
        continue

    line = line.rstrip()

    if line.startswith("```"):
        in_fenced_block = not in_fenced_block
        continue

    if in_fenced_block:
        continue

    m = header_re.search(line)
    if not m:
        continue

    level = len(m.group(1)) - 1
    text = m.group(2).strip().replace("\\", "")

    if text.lower() == "table of contents":
        continue

    if level > max_level:
        continue

    link_id = "".join(
        [
            c
            for c in text.lower().replace(" ", "-")
            if c not in ["\\", ".", ",", "`", "`", '"', "'"]
        ]
    )
    link = "#" + link_id

    indent = " " * 4 * level

    print(f"{indent}- [{text}]({link})")
