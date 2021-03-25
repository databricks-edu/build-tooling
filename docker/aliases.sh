#@IgnoreInspection BashAddShebang
# Aliases and functions to make using the build tools within Docker easier.
#
# Source this file from within your .bashrc, .bash_profile or .zshrc file.
#
#    . /path/to/build-tooling/docker/aliases.sh

# Set BUILD_TOOL_DOCKER_TAG to a different tag (e.g., "snapshot") to use
# a different tag.

: ${BUILD_TOOL_DOCKER_TAG:=latest}

for i in aws bdc course databricks dev gendbc \
         jup master_parse update_tools update-tools
do
  unalias $i 2>/dev/null
  unset -f $i 2>/dev/null
done

function run_command_via_image {
  COMMAND=$1
  if [ -n "$COMMAND" ]; then
    shift
  fi
  docker run -it --rm \
    -p 8888:8888 \
    -v `pwd`:/home/jovyan/work \
    -v $HOME/.aws:/home/jovyan/.aws \
    -v $HOME/.databricks:/home/jovyan/.databricks \
    databrickseducation/build-tool:$BUILD_TOOL_DOCKER_TAG $COMMAND "$@"
}

alias dev="run_command_via_image bash"
alias jup="run_command_via_image"

function aws {
  run_command_via_image aws "$@"
}
function bdc {
  run_command_via_image bdc "$@"
}
function course {
  run_command_via_image course "$@"
}
function databricks {
  run_command_via_image databricks "$@"
}
function gendbc {
  run_command_via_image gendbc "$@"
}
function master_parse {
  run_command_via_image master_parse "$@"
}

function update_tools {
  curl -L "https://git.io/fhaLg" | bash
}

alias update-tools=update_tools
