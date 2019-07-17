#!/usr/bin/env bash
#
# Use this script to run the uninstalled (repo) version of "bdc",
# pulling "gendbc", and "master_parse" from the repo.
# -----------------------------------------------------------------------------

here=`pwd`

export PYTHONPATH=.:db_edu_util:master_parse:gendbc
python bdc/__init__.py "$@"
