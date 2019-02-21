#@IgnoreInspection BashAddShebang
# Aliases and functions to make using the build tools within Docker easier.
#
# Source this file from within your .bashrc, .bash_profile or .zshrc file.
#
#    . /path/to/build-tooling/docker/aliases.sh

# Set BUILD_TOOL_DOCKER_TAG to a different tag (e.g., "snapshot") to use
# a different tag.
: ${BUILD_TOOL_DOCKER_TAG:=latest}
alias bdc="docker run -it --rm -w `pwd` -e DB_SHARD_HOME=$DB_SHARD_HOME -e HOME=$HOME -v $HOME:$HOME databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG bdc"
alias databricks="docker run -it --rm -w `pwd` -e HOME=$HOME -v $HOME:$HOME databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG databricks"
alias gendbc="docker run -it --rm -w `pwd` -e HOME=$HOME -v $HOME:$HOME databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG gendbc"
alias master_parse="docker run -it --rm -w `pwd` -e HOME=$HOME -v $HOME:$HOME databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG master_parse"

COURSE_ENV_VARS="DB_CONFIG_PATH DB_PROFILE DB_SHARD_HOME COURSE_NAME COURSE_REPO COURSE_HOME COURSE_YAML COURSE_MODULES COURSE_REMOTE_SOURCE COURSE_REMOTE_TARGET PREFIX SOURCE TARGET EDITOR PAGER LESS LESSCHARSET USER"

function create_course_envfile {
  : ${1?'Missing file name'}
  egrep=`echo $COURSE_ENV_VARS | sed 's/ /|/g'`
  env | egrep "$egrep" >$1
}

# The course tool can look at a lot of environment variables. To ease passing
# the entire environment into the tool, this "alias" is defined as a function.

function course {

  : ${BUILD_TOOL_DOCKER_TAG:=latest}

  TMP_ENV=/tmp/course-env.$$

  create_course_envfile $TMP_ENV

  docker run -it --rm -w `pwd` --env-file $TMP_ENV -e HOME=$HOME -v $HOME:$HOME databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG course "$@"

  rm -f $TMP_ENV
}


