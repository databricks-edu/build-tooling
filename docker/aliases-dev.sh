function dbe {
  usage="dbe [latest|dev]"
  case $# in
    1)
      case "$1" in
        latest|dev)
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
