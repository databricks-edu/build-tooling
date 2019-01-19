#!/usr/bin/env bash
#
# Install or upgrade the Docker-based build tools.


IMAGE='databrickseducation/build-tool'

echo "Pulling $IMAGE ..."
docker pull $IMAGE

echo "Updating aliases ..."
curl -o $HOME/.build-tools-aliases.sh https://raw.githubusercontent.com/databricks-edu/build-tooling/master/docker/aliases.sh

echo "Done!"

