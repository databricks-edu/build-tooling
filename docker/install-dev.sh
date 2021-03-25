#!/usr/bin/env bash
#
# Install the development version of the build tools from the remote branch 'dev'

cp Dockerfile Dockerfile.dev
sed '/master/dev' <Dockerfile >Dockerfile.dev

docker build -t databrickseducation/build-tool:dev .
# rm -rf Dockerfile.dev

echo "Copy local aliases to root"
cp aliases.sh ~/.build-tool-aliases.sh
. ~/.build-tool-aliases.sh

dbe dev
