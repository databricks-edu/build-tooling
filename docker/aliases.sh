#@IgnoreInspection BashAddShebang
# Aliases and functions to make using the build tools within Docker easier.
#
# Source this file from within your .bashrc, .bash_profile or .zshrc file.
#
#    . /path/to/build-tooling/docker/aliases.sh

# Set BUILD_TOOL_DOCKER_TAG to a different tag (e.g., "snapshot") to use
# a different tag.

: ${BUILD_TOOL_DOCKER_TAG:=latest}

for i in bdc databricks gendbc master_parse course dbe \
         update_tools update-tools
do
  unalias $i 2>/dev/null
  unset -f $i 2>/dev/null
done

function dbe {
  usage="dbe [latest|snapshot]"
  case $# in
    1)
      case "$1" in
        latest|snapshot)
          export BUILD_TOOL_DOCKER_TAG=$1
          dbe
          ;;
        *)
          echo "$usage" >&2
          return 1
          ;;
      esac
      ;;

    0)
      image=databrickseducation/build-tool:${BUILD_TOOL_DOCKER_TAG:-latest}
      echo "Using build tools in Docker image $image"
      ;;

    *)
      echo "$usage" >&1
      return 1
      ;;
  esac
  return 0
}

function bdc {
  docker run -i --rm -w `pwd` -e DB_SHARD_HOME=$DB_SHARD_HOME \
             -e COLUMNS=$COLUMNS -e HOME=$HOME -v $HOME:$HOME \
             databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG bdc "$@"
}

function databricks {
  docker run -it --rm -w `pwd` -e COLUMNS=$COLUMNS -e HOME=$HOME -v $HOME:$HOME \
    databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG databricks "$@"
}

function gendbc {
  docker run -it --rm -w `pwd` -e COLUMNS=$COLUMNS -e HOME=$HOME -v $HOME:$HOME \
    databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG gendbc "$@"
}

function master_parse {
  docker run -it --rm -w `pwd` -e COLUMNS=$COLUMNS -e HOME=$HOME -v $HOME:$HOME \
    databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG master_parse "$@"
}

COURSE_ENV_VARS="DB_CONFIG_PATH DB_PROFILE DB_SHARD_HOME COLUMNS COURSE_NAME COURSE_REPO COURSE_HOME COURSE_YAML COURSE_MODULES COURSE_REMOTE_SOURCE COURSE_REMOTE_TARGET PREFIX SOURCE TARGET EDITOR PAGER LESS LESSCHARSET USER"

unset -f create_course_envfile 2>/dev/null

function create_course_envfile {
  : ${1?'Missing file name'}
  egrep=`echo $COURSE_ENV_VARS | sed 's/ /|/g'`
  env | egrep "$egrep" >$1
}

# The course tool can look at a lot of environment variables. To ease passing
# the entire environment into the tool, this "alias" is defined as a function.

function course {

  TMP_ENV=/tmp/course-env.$$

  create_course_envfile $TMP_ENV

  docker run -it --rm -w `pwd` --env-file $TMP_ENV -e HOME=$HOME -v $HOME:$HOME databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG course "$@"

  rm -f $TMP_ENV
}

function update_tools {
  local usage="Usage: $0 [latest|snapshot]"
  local tag=latest

  case "$#" in
    0)
      ;;
    1)
      case "$1" in
        latest|snapshot)
          tag=$1
          ;;
        *)
          echo $usage >&2
          return 1
          ;;
      esac
      ;;
    *)
      echo $usage >&2
      return 1
      ;;
  esac

  echo "Updating tools from $tag"

  local url="https://git.io/fhaLg"
  case "$tag" in
    latest)
      curl -L $url | bash
      ;;
    snapshot)
      curl -L $url | bash -s snapshot
      ;;
  esac
}

alias update-tools=update_tools

