# Pristine Python 3 environment

This directory contains a Dockerfile that creates a pristine Python 3 
Docker image, with nothing extra installed. This environment is useful 
for cleanroom testing of the build tools.

## Create the image

Run `./install.sh` to create a `pristine-python3` Docker image. This image:

- runs all commands as non-`root` user `user`
- contains Python 3, as well as a virtual environment `/usr/local/pythons/3`
  (owned by `user`)
- ensures if you invoke `bash` or `zsh` within the instance, your default
  Python is the one in the virtual environment.

Every time you fire up the image, you get an instance with a clean Python 3
environment into which you can install the build tools (or anything else).

Other notable aspects of the image:

- The password for `user` is `user`.
- `sudo` is installed, and `user` is in the `/etc/sudoers` file.

## Source the aliases file 

The `aliases.sh` file defines alias (really, a shell function) called `py3dock`.
This command launches an instance of the image, running `bash` or `zsh` 
(depending on the value of `$SHELL` on your laptop).

For convenience, you can also invoke `pydock3`.
