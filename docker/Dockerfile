FROM jupyter/minimal-notebook

USER root
RUN apt-get update && apt-get install -y groff jq less zip

USER jovyan
RUN pip install git+https://github.com/databricks-edu/build-tooling@master
COPY course-static /home/jovyan/static
COPY course-static/templates/ilt.revealjs /home/jovyan/.pandoc/templates/default.revealjs
WORKDIR /home/jovyan/work
