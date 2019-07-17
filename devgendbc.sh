#!/usr/bin/env bash
#
# Use this script to run the uninstalled (repo) version of "gendbc",
# pulling "db_edu_util" from the repo.
# -----------------------------------------------------------------------------

here=`pwd`

export PYTHONPATH=.:db_edu_util
python gendbc/__init__.py "$@"
