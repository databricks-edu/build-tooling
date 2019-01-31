#!/usr/bin/env bash
#
# Use this script to run the uninstalled (repo) version of "gendbc",
# pulling "notebooktools" from the repo.
# -----------------------------------------------------------------------------

here=`pwd`
up=`(cd ..; pwd)`

PYTHONPATH=.:$up/notebooktools python gendbc/__init__.py "$@"
