#!/bin/sh
curl -O https://raw.githubusercontent.com/docker-library/openjdk/master/8/jdk/Dockerfile
sed -i.bak 's/FROM buildpack-deps:stretch-scm/FROM python:2/' Dockerfile
sed -i.bak 's/update.sh/create_image.sh/' Dockerfile
echo 'RUN pip install git+https://github.com/databricks-edu/build-tooling' >> Dockerfile
echo 'RUN apt-get update && apt-get install less' >> Dockerfile
echo 'RUN mv /root/local/bin/gendbc /usr/local/bin/' >> Dockerfile
cp ../course .
echo 'ADD course /usr/local/bin' >> Dockerfile

if [ "$1" != "" -a "$1"=="build" ]; then
    docker build -t build-tool .
fi
rm Dockerfile.bak course
