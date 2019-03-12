#!/usr/bin/env bash

# Runs the unit tests.

VENV='.venv'

function banner {
  echo ''
  echo '********************'
  echo "$*"
  echo '********************'
  echo ''
}

usage="run-tests.sh [travis]"

update_venv=true

case "$#" in
  0)
    ;;
  1)
    if [ "$1" != "travis" ]
    then
      echo $usage >&2
      exit 1
    fi
    update_venv=false
    ;;
  *)
    echo $usage >&2
    exit 1
    ;;
esac

packages="bdc gendbc db_edu_util course master_parse"
test_dirs=
for p in $packages
do
  if [ -d $p/test ]
  then
    test_dirs="$test_dirs $p/test"
  fi
done

if [ "$update_venv" = "true" ]
then
  if [ ! -d $VENV ]
  then
    banner "Creating virtual environment in $VENV"
    virtualenv $VENV
  fi

  . $VENV/bin/activate

  echo Using $(type -p python)

  banner "Reinstalling build tools and test harness"
  python setup.py install
  pip install pytest
fi

failed=false
here=`pwd`
for d in $test_dirs
do
  cd $d || exit 1
  banner "Running tests in $d"
  pytest -W ignore -ra --cache-clear .
  if [ $? -ne 0 ]
  then
    failed=true
  fi
  cd $here
done

if [ $failed = true ]
then
  banner "Tests failed."
  exit 1
fi

exit 0
