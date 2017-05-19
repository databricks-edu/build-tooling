#!/bin/sh
#
# Front-end Unix shell script for the gendbc tool.
#

vm_opts=
while [ $# -gt 0 ]
do
  case "$1" in
    -D*|-X*)
      vm_opts="$vm_opts $1"
      shift
      ;;
    *)
      break
      ;;
  esac
done

if [ -z $JAVA_HOME ]
then
  export JAVA_HOME="@JAVA_HOME@"
fi

if [ "$GENDBC_SCALA_OPTS" != "" ]
then
  vm_opts="$vm_opts $GENDBC_SCALA_OPTS"
fi

JAR=@JAR@

exec "$JAVA_HOME"/bin/java -jar "$JAR" "${@}"
