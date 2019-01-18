#!/bin/sh

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

: ${FORK:=databricks-edu}
: ${PIP_TARGET:=git+https://github.com/$FORK/build-tooling}

echo "Creating $DOCKERFILE"

echo "FROM python:2" >$DOCKERFILE
echo "RUN pip install $PIP_TARGET" >> $DOCKERFILE
echo 'RUN apt-get update && apt-get install -y less zip unzip vim' >> $DOCKERFILE

USAGE=

case "$op" in
    "")
        ;;
    "build")
        docker build -t build-tool $DOCKERFILEDIR
        ;;
    "rebuild")
        docker rmi build-tool
        docker build --no-cache -t build-tool $DOCKERFILEDIR
        ;;
esac

#rm -rf $DOCKERFILEDIR
echo $DOCKERFILE
