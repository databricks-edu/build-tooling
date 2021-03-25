#!/usr/bin/env bash
#
# Install the development version of the build tools from the remote branch 'dev'

sed 's/master/dev/' Dockerfile > Dockerfile.dev
docker build -t databrickseducation/build-tool:dev -f Dockerfile.dev . "$@"
# rm -rf Dockerfile.dev

echo "Copy local aliases to root"
cp aliases.sh ~/.build-tool-aliases.sh
. ~/.build-tool-aliases.sh
. aliases-dev.sh

rm Dockerfile.dev
dbe dev
