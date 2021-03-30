#!/usr/bin/env python

"""
Pandoc filter to convert all regular text to uppercase.
Code, link URLs, etc. are not affected.
"""
import json
from pathlib import Path
from pandocfilters import toJSONFilter, Header


def hrToHeader(key, value, format, meta):
    if key == 'Header':
        Path('current-header').unlink(missing_ok=True)
        with open('current-header', 'w') as current_header:
            current_header.write(json.dumps(value))
    if key == 'HorizontalRule':
        with open('current-header', 'r') as current_header:
            value = json.loads(current_header.read())
            [ident, classes, keyvals] = value
            return Header(ident, classes, keyvals)#

if __name__ == "__main__":
    toJSONFilter(hrToHeader)
