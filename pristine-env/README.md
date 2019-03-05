# Pristine Python 3 environment

This directory contains a Dockerfile that creates a pristine Python 3 
Docker image, with nothing extra installed. This environment is useful 
for cleanroom testing of the build tools.

When you fire up the image, by virtual of the `py3dock` alias (see below),
you get an Ubuntu instance with a pristine version of Python 3. You can install
the build tools (or anything else) and run tests. When you exit the image,
everything just goes away, and the next time you fire up the image, you start
all over again with a clean environment. 

## Create the image

Run `./install.sh` to create a `pristine-python3` Docker image. This image:

- runs all commands as non-`root` user `user`
- contains Python 3, as well as a virtual environment `/usr/local/pythons/3`
  (owned by `user`)
- ensures if you invoke `bash` or `zsh` within the instance, your default
  Python is the one in the virtual environment.

Other notable aspects of the image:

- The password for `user` is `user`.
- `sudo` is installed, and `user` is in the `/etc/sudoers` file.

## Source the aliases file 

The `aliases.sh` file defines alias (really, a shell function) called `py3dock`.
This command launches an instance of the image, running `bash` or `zsh` 
(depending on the value of `$SHELL` on your laptop).

For convenience, you can also invoke `pydock3`.
