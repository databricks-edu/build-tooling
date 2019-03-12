FROM python:3.7-stretch

# Update the package manager
RUN apt-get update

# Install packages needed by WeasyPrint. See
# https://weasyprint.readthedocs.io/en/latest/install.html#linux
RUN apt-get install -y build-essential python3-dev python3-pip \
  python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 \
  libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info

# Install packages that make life a bit easier.
RUN apt-get install -y less zip unzip vim nano zsh sudo man autojump

# Add a non-root user.
RUN groupadd -g 1001 user
RUN useradd -r -u 1001 -g user user
RUN echo 'user:user' | chpasswd
RUN echo "user ALL=(ALL:ALL) ALL" >>/etc/sudoers
RUN ln -s /home /Users

# Upgrade pip and create a virtual environment owned by "user".
RUN pip install --upgrade pip
RUN pip install virtualenv
RUN mkdir -p /usr/local/pythons
RUN virtualenv /usr/local/pythons/3
RUN chown -R user /usr/local/pythons/3

# Ensure that the virtual environment is the default Python, when shells
# are involved.
RUN echo '. /usr/local/pythons/3/bin/activate' >/etc/zshrc
RUN chmod 644 /etc/zshrc
RUN echo '. /usr/local/pythons/3/bin/activate' >/etc/bashrc
RUN chmod 644 /etc/bashrc

# The container runs as "user".
USER user
