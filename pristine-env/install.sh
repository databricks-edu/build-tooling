#!/usr/bin/env bash
#

IMAGE='pristine-python3'

here=$(dirname $0)
here=$(pwd)
cd $here || exit 1

echo "Building $IMAGE Docker image"
echo ""
docker build -t $IMAGE .

echo "Be sure to source $here/aliases.sh"
