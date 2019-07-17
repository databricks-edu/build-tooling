#!/usr/bin/env bash
#
# Use this script to run the uninstalled (repo) version of "course",
# pulling "bdc", "gendbc", and "master_parse" from the repo.
# -----------------------------------------------------------------------------

here=`pwd`

export PYTHONPATH=.:db_edu_util:master_parse:gendbc:bdc
python course/__init__.py "$@"
