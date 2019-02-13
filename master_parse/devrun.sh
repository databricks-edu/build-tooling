#!/usr/bin/env bash
#
# Use this script to run the uninstalled (repo) version of "master_parse",
# pulling "db_edu_util" from the repo.
# -----------------------------------------------------------------------------

here=`pwd`
up=`(cd ..; pwd)`

PYTHONPATH=.:$up/db_edu_util python master_parse/__init__.py "$@"
