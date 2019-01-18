#!/usr/bin/env bash
#
# Use this script to run the uninstalled (repo) version of "course",
# pulling "bdc", "gendbc", and "master_parse" from the repo.
# -----------------------------------------------------------------------------

here=`pwd`
up=`(cd ..; pwd)`

PYTHONPATH=.:$up/master_parse:$up/gendbc:$up/bdc python course/__init__.py "$@"
