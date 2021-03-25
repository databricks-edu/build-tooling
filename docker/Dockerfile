# NOTE: Make sure build caching is OFF, or Docker may not pick up the
# latest version of the tools.
FROM jupyter/base-notebook

USER root
RUN apt-get update && apt-get install -y git groff jq less nano vim unzip zip

USER jovyan
RUN pip install git+https://github.com/databricks-edu/build-tooling@master
