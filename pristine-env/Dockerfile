# NOTE: Make sure build caching is OFF, or Docker may not pick up the
# latest version of the tools.
FROM python:3
RUN apt-get update && apt-get install -y less zip unzip vim nano zsh sudo man 

RUN groupadd -g 1001 user
RUN useradd -r -u 1001 -g user user
RUN echo 'user:user' | chpasswd
RUN echo "user ALL=(ALL:ALL) ALL" >>/etc/sudoers
RUN ln -s /home /Users

RUN pip install --upgrade pip
RUN pip install virtualenv
RUN mkdir -p /usr/local/pythons
RUN virtualenv /usr/local/pythons/3
RUN chown -R user /usr/local/pythons/3

RUN echo '. /usr/local/pythons/3/bin/activate' >/etc/zshrc
RUN chmod 644 /etc/zshrc
RUN echo '. /usr/local/pythons/3/bin/activate' >/etc/bashrc
RUN chmod 644 /etc/bashrc

USER user
