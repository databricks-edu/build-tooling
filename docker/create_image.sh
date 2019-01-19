#!/bin/sh
#
# NOTE: You can override the way pip installs the build tools by specifying
# a PIP_TARGET. This is useful during development. For example, to load
# the tools from bmc's fork, using branch "coursework", you can do this:
#
# PIP_TARGET=git+https://github.com/bmc/build-tooling.git@coursework ./create_image.sh rebuild
#
# By default, it uses the master branch of the databricks-edu/build-tooling
# repo.

USAGE="$0 build|rebuild"

DOCKERFILEDIR=/tmp/build-tool.$$

mkdir $DOCKERFILEDIR || exit 1

DOCKERFILE=$DOCKERFILEDIR/Dockerfile

THIS_DIR=`dirname $0`
case "$THIS_DIR" in
    ""|.)
        THIS_DIR=`pwd`
        ;;
    *)
        ;;
esac
cd $THIS_DIR

op=

case $# in
    1)
        case "$1" in
            "build")
                op=build
                ;;
            "rebuild")
                op=rebuild
                ;;
            *)
                echo $USAGE >&1
                exit 1
                ;;
        esac
        ;;
    *)
        echo $USAGE >&2
        exit 1
        ;;
esac

: ${PIP_TARGET:=git+https://github.com/databricks-edu/build-tooling}

echo "Creating $DOCKERFILE"

echo "FROM python:2" >$DOCKERFILE
# This file is used by the tooling to tell that it is inside Docker.
echo 'RUN touch /etc/in-docker' >>$DOCKERFILE
echo "RUN pip install $PIP_TARGET" >> $DOCKERFILE
echo 'RUN apt-get update && apt-get install -y less zip unzip vim nano' >> $DOCKERFILE
echo 'RUN curl "https://s3.amazonaws.com/aws-cli/awscli-bundle.zip" -o "awscli-bundle.zip"' >> $DOCKERFILE
echo 'RUN unzip awscli-bundle.zip' >> $DOCKERFILE
echo 'RUN ./awscli-bundle/install -i /usr/local/aws -b /usr/local/bin/aws' >> $DOCKERFILE


USAGE=

case "$op" in
    "")
        ;;
    "build")
        echo 'Building Docker image "build-tool"'
        docker build -t build-tool $DOCKERFILEDIR
        ;;
    "rebuild")
        echo 'Removing existing 'build-tool' Docker image'
        docker rmi build-tool
        echo 'Building "build-tool" Docker image'
        docker build --no-cache -t build-tool $DOCKERFILEDIR
        ;;
esac

#rm -rf $DOCKERFILEDIR
echo $DOCKERFILE
