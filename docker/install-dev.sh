#!/usr/bin/env bash
#
# Install the development version of the build tools from a tarball of the local library

sed '/RUN pip.*git+https.*$/d' Dockerfile >Dockerfile.dev

here=$(pwd)
parent=$(cd ..; pwd)

# Create the tarball.
cd $parent
echo "Tarring up the local repo."
mkdir -p $HOME/tmp
tar czf $HOME/tmp/source.tgz --exclude='.git' .
cp $HOME/tmp/source.tgz $here
echo "Done creating the tarball."

# Append the tarball stuff to the Dockerfile. Remember: ADD unpacks
# archives.

cd $here
sed '/RUN pip.*git+https.*$/d' Dockerfile >Dockerfile.dev
cat <<EOF >>Dockerfile.dev
RUN pip install awscli>=1.19.36 beautifulsoup4>=4.9.0 click>=7.1.2 databricks-cli>=0.8.7 docopt>=0.6.2 GitPython>=3.1.2 grizzled-python>=2.2.0 markdown2>=2.3.7 pandocfilters>=1.3.0 parsimonious>=0.8.1 pypandoc>=1.5 pystache>=0.5.4 PyYAML>=5.1 nbformat>=4.4.0 requests>=2.22.0 termcolor>=1.1.0 WeasyPrint>=45
RUN mkdir /tmp/build-tools
ADD source.tgz /tmp/build-tools

USER root
RUN chown -R jovyan:users /tmp/build-tools

USER jovyan
RUN cd /tmp/build-tools && python setup.py install
EOF

docker build -t databrickseducation/build-tool:dev -f Dockerfile.dev . "$@"
rm Dockerfile.dev
rm $HOME/tmp/source.tgz

echo "Copy local aliases to root"

cp aliases.sh ~/.build-tool-aliases.sh
. ~/.build-tool-aliases.sh
. aliases-dev.sh

dbe dev
