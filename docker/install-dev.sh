#!/usr/bin/env bash
#
# Install the development version of the build tools from the local repo
# clone (i.e., local directory) into a Docker images. Useful for development
# and debugging.
#
# Image defaults to databrickseducation/build-tool:snapshot

case "$#" in
  0)
    image="databrickseducation/build-tool:snapshot"
    ;;
  1)
    image=$1
    ;;
  *)
    echo "Usage: $0 [dockerimage]" >&2
    exit 1
    ;;
esac

here=$(dirname $0)
here=$(pwd)
parent=$(cd ..; pwd)

tmp=/tmp/build.$$
mkdir $tmp || exit 1
# Delete the pip install of the tools from the Dockerfile. We'll install manually,
# from a unpacked tarball.
sed '/RUN pip.*git+https.*$/d' <Dockerfile >$tmp/Dockerfile

# Create the tarball.
cd $parent
echo "Tarring up the local repo."
tar czf $tmp/source.tgz .
echo "Done creating the tarball."

# Append the tarball stuff to the Dockerfile. Remember: ADD unpacks
# archives.
cat <<EOF >>$tmp/Dockerfile
RUN mkdir /tmp/build-tools
ADD source.tgz /tmp/build-tools
RUN cd /tmp/build-tools && python setup.py install
EOF
cd $tmp

echo "Creating Docker image $image"
docker build -t $image .
echo "Done."
echo ""
echo "Installed local repo to $image"
cd $here
rm -rf $tmp
