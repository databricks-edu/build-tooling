# NOTE: Make sure build caching is OFF, or Docker may not pick up the
# latest version of the tools.
FROM python:2
RUN touch /etc/in-docker
RUN pip install git+https://github.com/databricks-edu/build-tooling
RUN apt-get update && apt-get install -y less zip unzip vim nano
RUN curl "https://s3.amazonaws.com/aws-cli/awscli-bundle.zip" -o "awscli-bundle.zip"
RUN unzip awscli-bundle.zip
RUN ./awscli-bundle/install -i /usr/local/aws -b /usr/local/bin/aws
