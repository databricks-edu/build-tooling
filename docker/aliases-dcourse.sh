


COURSE_ENV_VARS="DB_CONFIG_PATH DB_PROFILE DB_SHARD_HOME COLUMNS COURSE_NAME COURSE_REPO COURSE_HOME COURSE_YAML COURSE_MODULES COURSE_REMOTE_SOURCE COURSE_REMOTE_TARGET PREFIX SOURCE TARGET EDITOR PAGER LESS LESSCHARSET USER"

unset -f create_course_envfile 2>/dev/null

function create_course_envfile {
  : ${1?'Missing file name'}
  egrep=`echo $COURSE_ENV_VARS | sed 's/ /|/g'`
  env | egrep "$egrep" >$1
}

# The course tool can look at a lot of environment variables. To ease passing
# the entire environment into the tool, this "alias" is defined as a function.

function dcourse {

  TMP_ENV=/tmp/dcourse-env.$$

  create_course_envfile $TMP_ENV

  docker run -it --rm -w `pwd` --env-file $TMP_ENV -e HOME=$HOME -v $HOME:$HOME databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG dcourse "$@"

  rm -f $TMP_ENV
}
