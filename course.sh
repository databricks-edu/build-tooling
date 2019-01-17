#!/bin/bash
set -e
CONFIG_FILE=~/.databricks/course.config
VERSION=1.1.2

if [ -f "${CONFIG_FILE}" ]; then
  . "${CONFIG_FILE}"
fi

export EDITOR="${EDITOR:-"open -t"}"
export PAGER="${PAGER:-"less --RAW-CONTROL-CHARS"}"

if [ -z "$COURSE_REPO" ]; then
  COURSE_REPO="${REPO:-"${HOME}/repos/training"}"
fi

function configure() {
  if [ "${CONFIGURE_COMPLETE}" == "true" -a "$1" != "force" ]; then
    return
  else
    CONFIGURE_COMPLETE=true
  fi

  if [ -z "${COURSE_NAME}" -a "$*" != "help" ]; then
    echo "ERROR: An active course must first be set using the following:"
    echo "  course work-on [name]"
    echo ""
    exit 2
  fi

  # Navigation logic for self-paced courses
  SELF_PACED_COURSES="Structured-Streaming Spark-SQL DataFrames ETL-Part-1 ETL-Part-2 ETL-Part-3 Delta"
  if  [[ "${SELF_PACED_COURSES}" =~ (^|[[:space:]])"${COURSE_NAME}"($|[[:space:]]) ]]; then
    PREFIX="${PREFIX:-"Self-Paced/"}"
  else
    PREFIX="${PREFIX:-""}"
  fi

  # Each of the variables below can be set prior to running the script.
  # If the variable isn't preset then the default is used.
  export DB_PROFILE="${DB_PROFILE:-"DEFAULT"}"
  DB_CONFIG_PATH="${DB_CONFIG_PATH:-"${HOME}/.databrickscfg"}"
  COURSE_AWS_PROFILE="${COURSE_AWS_PROFILE:-"default"}"
  COURSE_HOME="${COURSE_HOME:-"${COURSE_REPO}/courses/${PREFIX}${COURSE_NAME}"}"
  COURSE_YAML="${COURSE_YAML:-"${COURSE_HOME}/build.yaml"}"
  COURSE_MODULES="${COURSE_MODULES:-"${COURSE_REPO}/modules/${PREFIX}${COURSE_NAME}"}"
  SOURCE="${SOURCE:-"_Source"}"
  TARGET="${TARGET:-"_Target"}"
  SOURCE_PATH="${COURSE_REPO}/courses/${PREFIX}/${COURSE_NAME}"
  if ! bdc --info "${COURSE_YAML}"; then
    echo "Aborting: Error reading/parsing ${COURSE_YAML}" 1>&2
    exit 1
  fi
  eval `bdc --info --shell "${COURSE_YAML}"`
  export COURSE_NAME COURSE_VERSION
  COURSE_LOWERCASE="`echo "${COURSE_NAME}" | tr '[:upper:]' '[:lower:]'`"
  DEPLOY_PATH="s3://files.training.databricks.com/courses/${COURSE_LOWERCASE}"
  SOURCE_IMAGES="${COURSE_REPO}/modules/${PREFIX}/${COURSE_NAME}/images"
  DEPLOY_IMAGES="${DEPLOY_PATH}/${COURSE_VERSION}/images"

  # If DB_SHARD_HOME is not yet, then read it from .databrickscfg.
  if [ -f "${DB_CONFIG_PATH}" ]; then
    if [ -z "${DB_SHARD_HOME}" ]; then
      # Extract the home from .databrickscfg
      DB_SHARD_HOME=`sed '
        '"/${DB_PROFILE}/"',/^[ \t]*$/ {
          /^home = / {
            s/^home = //
            b
          }
        }
        d
      ' "${DB_CONFIG_PATH}"`
    fi
    if [ -z "${DB_SHARD_HOME}" ]; then
      # Failback to reading the username from .databrickscfg
      DB_SHARD_HOME=`sed '
        '"/\[${DB_PROFILE}\]/"',/^[ \t]*$/ {
          /^username = token$/ d
          /^username = / {
            s/^username = /\/Users\//
            b
          }
        }
        d
      ' "${DB_CONFIG_PATH}"`
    fi
  fi

  if [ -z "${COURSE_REMOTE_SOURCE}" ]; then
    if [ -z "${DB_SHARD_HOME}" ]; then
      echo The COURSE_REMOTE_SOURCE or DB_SHARD_HOME environment variable must be set.
      exit 1
    fi
    COURSE_REMOTE_SOURCE="${DB_SHARD_HOME%/}/${SOURCE}/${COURSE_NAME}"
  fi
  if [ -z "${COURSE_REMOTE_TARGET}" ]; then
    if [ -z "${DB_SHARD_HOME}" ]; then
      echo The COURSE_REMOTE_TARGET or DB_SHARD_HOME environment variable must be set.
      exit 1
    fi
    COURSE_REMOTE_TARGET="${DB_SHARD_HOME%/}/${TARGET}/${COURSE_NAME}"
  fi
}

pager() {
  if [ -t 1 ]; then
    ${PAGER}
  else
    cat
  fi
}

help() {
  cat <<EOF | pager
NAME:
    course

DESCRIPTION:
    Tool for developing Databricks courses.

USAGE:
    course help              # Show this usage syntax.
    course install-tools     # Install this script and latest build-tools.
    course work-on <name>    # Specify and remember the course to build.
    course download build    # Download from SOURCE, Build to TARGET
    course download difftool # View what's changed in the course.
    course build             # Build and uploads to TARGET.
    course upload            # Upload latest SOURCE from local git.
    course clean             # Remove TARGET from the server.
    course clean-source      # Remove SOURCE from the server.
    course home              # Open the folder containing the build.yaml.
    course modules           # Open the folder containing the course modules.
    course repo              # Open the root of the training repo in git.
    course yaml              # Edit the build yaml.
    course script            # Edit the course script (this program)
    course config            # Edit your course script configuration settings.
    course guide             # Open the instructor guide.
    course stage             # Deploy a build to s3 staging area.
    course release           # Deploy a build to s3 release directory.
    course deploy-images     # Deploy the image files to s3.
    course grep <pattern>    # Search for text in notebooks.
    course sed <commands>    # Search/replace text in notebooks using 'sed -E'.
    course xargs <command>   # Run the provided command once per notebook.
    course set CONF=VAL      # Configure and save an environment setting.

CONFIGURATION:
    A course name must be provided.  You can set a default course name using:
        $ course work-on spark-sql
    Or you can set a temporary override using the command line:
        $ course --name spark-sql build
    And lastly, you can also configure it as COURSE_NAME in:
         ~/.databricks/course.config

ENVIRONMENT VARIABLES:
    DB_CONFIG_PATH: Path to .databrickscfg
        Default: ~/.databrickscfg
        Current: ${DB_CONFIG_PATH}
    DB_PROFILE: Profile to use within .databrickscfg profile
        Default: DEFAULT
        Current: ${DB_PROFILE}
    DB_SHARD_HOME: Workspace path for home folder
        Default: /Users/[Username]
        Current: ${DB_SHARD_HOME}
    COURSE_NAME: Name of the course you wish to build.
        Default: This must be provided.
        Current: ${COURSE_NAME}
    COURSE_REPO: Path to git repo
        Default: ~/repos/training
        Current: ${COURSE_REPO}
    COURSE_HOME: Path to course in git repo
        Default: ~/repos/training/courses/[COURSE_NAME]
        Current: ${COURSE_HOME}
    COURSE_YAML: Path to the build.yaml
        Default: ~/repos/training/courses/[COURSE_NAME]/build.yaml
        Current: ${COURSE_YAML}
    COURSE_MODULES: Path to modules in git repo
        Default: ~/repos/training/modules/[COURSE_NAME]
        Current: ${COURSE_MODULES}
    COURSE_REMOTE_SOURCE: Workspace path for course source
        Default: ~/${SOURCE}/[COURSE_NAME]
        Current: ${COURSE_REMOTE_SOURCE}
    COURSE_REMOTE_TARGET: Workspace path for built course
        Default: ~/${SOURCE}/[COURSE_NAME]
        Current: ${COURSE_REMOTE_TARGET}
    PREFIX: Path to append to course names in git, such as /self-paced
        Default: "", unless it's a self-paced course.
        Current: ${PREFIX}
    SOURCE: Prefix for uploading/downloading source files.
        Default: _Source
        Current: ${SOURCE}
    TARGET: Prefix for uploading/downloading built files.
        Default: _Target
        Current: ${TARGET}
    EDITOR: Text editor program
        Default: open -a textedit
        Current: ${EDITOR}
    PAGER: Program to scroll text output
        Default: less --RAW-CONTROL-CHARS
        Current: ${PAGER}

EOF
}

clean() {
  (
    set -x
    databricks --profile "${DB_PROFILE}" workspace mkdirs "${COURSE_REMOTE_TARGET}"
    databricks --profile "${DB_PROFILE}" workspace rm --recursive "${COURSE_REMOTE_TARGET}"
  )
}

cleansource() {
  (
    set -x
    databricks --profile "${DB_PROFILE}" workspace mkdirs "${COURSE_REMOTE_SOURCE}"
    databricks --profile "${DB_PROFILE}" workspace rm --recursive "${COURSE_REMOTE_SOURCE}"
  )
}

upload() {
  (set -x; bdc --dprofile "${DB_PROFILE}" --upload "${COURSE_REMOTE_SOURCE}" "${COURSE_YAML}")
}

download() {
  (set -x; bdc --dprofile "${DB_PROFILE}" --download "${COURSE_REMOTE_SOURCE}" "${COURSE_YAML}")
  status
}

status() {
  (git status > /dev/null 2>&1 || cd "${COURSE_REPO}"; set -x; git status)
}

diff() {
  (
    git status > /dev/null 2>&1 || cd "${COURSE_REPO}"
    if [ -t 1 ]; then
      (set -x; git diff --color=always) | ${PAGER}
    else
      (set -x; git diff)
    fi
  )
}

difftool() {
  (git status > /dev/null 2>&1 || cd "${COURSE_REPO}"; set -x; git difftool --tool=opendiff --no-prompt)
}

import_dbc() {
  local dbc_path="$1"
  local upload_path="$2/${1#./}"
  local upload_path="${upload_path%/*}"
  # The "--language R" below is ignored by the databricks-cli but still required.
  (
    set -x;
    databricks workspace mkdirs --profile "${DB_PROFILE}" "${upload_path%/*}"
    databricks workspace import --profile "${DB_PROFILE}" --format DBC --language R "${dbc_path}" "${upload_path}"
  )
}
export -f import_dbc

build() {
  (set -x; bdc --overwrite "${COURSE_YAML}")
  clean
  (
    cd "${HOME}/tmp/curriculum/${COURSE_NAME}-${COURSE_VERSION}"
    find . -ipath '*.dbc' | xargs -I % bash -c "import_dbc \"%\" \"${COURSE_REMOTE_TARGET}\""
  )
}

stage() {
  release staging
}

release() {
  local deploy_type="${1:-"latest"}"
  if [ -f "${COURSE_HOME}/deploy.sh" ]; then
    DEPLOY_TYPE="${deploy_type}" "${COURSE_HOME}/deploy.sh"
  else
    build_target="${HOME}/tmp/curriculum/${COURSE_NAME}-${COURSE_VERSION}"
    (
      set -x
      bdc --overwrite "${COURSE_YAML}"
      # Uploading course
      aws s3 rm --profile "${COURSE_AWS_PROFILE}" --recursive "${DEPLOY_PATH}/${COURSE_VERSION}"
      aws s3 rm --profile "${COURSE_AWS_PROFILE}" --recursive "${DEPLOY_PATH}/${deploy_type}"
      echo "${COURSE_NAME}-${COURSE_VERSION}" | aws s3 cp --profile "${COURSE_AWS_PROFILE}" --cache-control "max-age=15" "-" "${DEPLOY_PATH}/${COURSE_VERSION}/version-${COURSE_VERSION}.txt"
      aws s3 cp --profile "${COURSE_AWS_PROFILE}" --cache-control "max-age=15" "${build_target}/amazon/Labs.dbc" "${DEPLOY_PATH}/${COURSE_VERSION}/amazon/Lessons.dbc"
      aws s3 cp --profile "${COURSE_AWS_PROFILE}" --cache-control "max-age=15" "${build_target}/azure/Labs.dbc" "${DEPLOY_PATH}/${COURSE_VERSION}/azure/Lessons.dbc"
      aws s3 cp --profile "${COURSE_AWS_PROFILE}" --cache-control "max-age=15" "${SOURCE_PATH}/index.html" "${DEPLOY_PATH}/${COURSE_VERSION}/index.html"
      aws s3 cp --profile "${COURSE_AWS_PROFILE}" --cache-control "max-age=15" "${SOURCE_PATH}/Course-Setup.html" "${DEPLOY_PATH}/${COURSE_VERSION}/Course-Setup.html"
      aws s3 cp --profile "${COURSE_AWS_PROFILE}" --cache-control "max-age=15" --recursive "${DEPLOY_PATH}/${COURSE_VERSION}" "${DEPLOY_PATH}/${deploy_type}"
    )
    deployimages
    echo ""
    echo "= ${COURSE_NAME} is now published to:"
    echo "https:${DEPLOY_PATH#s3:}/${deploy_type}/amazon/Lessons.dbc"
    echo "https:${DEPLOY_PATH#s3:}/${deploy_type}/azure/Lessons.dbc"
  fi
}

deployimages() {
  if [ -f "${COURSE_HOME}/deploy-images.sh" ]; then
    "${COURSE_HOME}/deploy-images.sh"
  elif [ -d "${SOURCE_IMAGES}" ]; then
    (set -x; aws s3 cp --profile "${COURSE_AWS_PROFILE}" --recursive --cache-control "max-age=300" --exclude "*.snagproj" "${SOURCE_IMAGES}" "${DEPLOY_IMAGES}")
  fi
}

yaml() {
  ${EDITOR} "${COURSE_YAML}"
}

guide() {
  ${EDITOR} "${COURSE_HOME}/Teaching-Guide.md"
}

script() {
  ${EDITOR} "$0"
}

config() {
  ${EDITOR} "${CONFIG_FILE}"
}

home() {
  open -a terminal "${COURSE_HOME}"
}

modules() {
  open -a terminal "${COURSE_MODULES}"
}

repo() {
  open -a terminal "${COURSE_REPO}"
}

do_xargs() {
  (set -x; bdc --list-notebooks "${COURSE_YAML}" | xargs -I {} "$@")
}

mygrep() {
  local filename="$1"
  shift
  if grep "$@" "${filename}" > /dev/null 2>&1; then
    echo "== ${filename}"
    grep "$@" "${filename}"
    echo ""
  fi
}
export -f mygrep

do_grep() {
  if [ -t 1 ]; then
    (do_xargs bash -c "mygrep {} --color=always "$@"") | ${PAGER}
  else
    do_xargs bash -c "mygrep {} "$@""
  fi
}

do_sed() {
  do_xargs sed -E -i "" -e "$1" {}
}

installtools() {
  if ! which realpath 2>&1 > /dev/null; then
    (set -x; brew install coreutils)
  fi
  if ! which aws 2>&1 > /dev/null; then
    (set -x; brew install awscli)
  fi
  local script=`realpath -m "$0"`
  if [ ! "${script}" == `realpath -m "${HOME}/local/bin/course"` ]; then
    if [ -e "${HOME}/local/bin/course" ]; then
      echo 'Unable to install ~/local/bin/course.  Another file already exists.'
      exit 1
    elif [ -h "${HOME}/local/bin/course" ]; then
      rm "${HOME}/local/bin/course"
    fi
    if [ ! -e ~/local/bin ]; then
      (set -x; mkdir -p ~/local/bin)
    fi
    (set -x; ln -s "${script}" ~/local/bin/course)
  fi
  (set -x; pip install --upgrade databricks-cli)
  (set -x; pip install --upgrade git+https://github.com/databricks-edu/build-tooling)
}

workon() {
  if [[ $# != 1 ]]; then
    cat <<EOF
Usage: course work-on <Course-Name>
EOF
    exit 2
  fi
  set_config COURSE_NAME="$1"
}

set_config() {
  for conf in "$@"; do
    eval "${conf}"
    configure force
  done
  while [ $# -gt 0 ]; do
    local setting="`echo \"${1%%=*}\" | tr '[:lower:]' '[:upper:]'`"
    local value="${1#*=}"
    if [ -z "${setting}" -o ! -z "${1##*=*}" ]; then
      echo ""
      echo "Usage: course set <setting>=<value>"
      exit 2
    fi
    eval "${setting}=${value}"
    mkdir -p "${CONFIG_FILE%/*}"
    if [ -f "${CONFIG_FILE}" ]; then
      local tempfile="`mktemp`"
      grep -v "^${setting}=" "${CONFIG_FILE}" >> "${tempfile}" && true
      cat "${tempfile}" > "${CONFIG_FILE}"
      rm "${tempfile}"
    fi
    if [ ! -z "${value}" ]; then
      echo "${setting}=\${${setting}:-\"${value}\"}" >> "${CONFIG_FILE}"
      echo "set ${setting}=${value}"
    else
      echo "unset ${setting}"
    fi
    shift
  done
}

if [ $# -eq 0 ]; then
  set -- help
fi

while [ $# -gt 0 ]; do
  cmd="$1"
  shift
  if [[ "${cmd}" =~ [^-]- ]]; then
    # Strip out any dashes in the command, other than leading dashes.
    cmd=`echo "${cmd}" | sed 's/-//g'`
  fi
  case "${cmd}" in
    version|--version|-v)
      echo $VERSION
      exit 0
      ;;
    help|--help|-h)
      help
    ;;
    set)
      set_config "$@"
      break
    ;;
    workon)
      workon "$1"
      shift
    ;;
    status|diff|difftool|script|config|installtools|repo)
      echo "=> cmd: ${cmd}"
      ${cmd}
    ;;
    clean|cleansource|upload|download|build|stage|deployimages|release|home|modules|yaml|guide)
      echo "=> cmd: ${cmd}"
      configure
      ${cmd}
    ;;
    grep|sed|xargs)
      configure
      "do_${cmd}" "$@"
      exit
    ;;
    name|--name|-n)
      COURSE_NAME="$1"
      CONFIGURE_COMPLETE=false
      shift
    ;;
    --trace)
      set -x
    ;;
    *)
      echo "Unknown option: ${cmd}"
      exit 1
    ;;
  esac
done

