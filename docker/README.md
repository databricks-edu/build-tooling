# Build Tool Docker Image

A Docker image capable defining a container capable of running the build tool
and its high-level wrapper `course` must have both Python 2.7 and the JDK.
Each of these exist as core images maintained by the Docker Team and available
via Docker Hub ([here](https://hub.docker.com/_/python/) and
[here](https://hub.docker.com/_/openjdk/)); however, as we require both, a
custom image must be built.

In order to be able to use the images maintained by the Docker Team, a script
is included that merges the two images, `create_image.sh`. Alternatively, this
script will also build the image for you.

## Install Docker

You will need a recent version of Docker. Use the Community Edition version
available at <https://store.docker.com>:

* [Mac edition](https://store.docker.com/editions/community/docker-ce-desktop-mac)
* [Windows edition](https://store.docker.com/editions/community/docker-ce-desktop-windows)
* [Other editions](https://store.docker.com/search?offering=community&type=edition)

Download it, and install it. Then, run it at least once (e.g., on the Mac,
open `/Applications/Docker.app`), which will create the various command line
links you'll need.

**WARNING**: On the Mac, do _not_ use the version of Docker that can be
installed via Homebrew. Some people have had problems with that version, and
we will not debug problems using the build tools in that environment. Use the
official Community Edition version, as noted above.

## To Create the `Dockerfile` and Build the Image

```
$ ./create_image.sh build
```

## Updating with New Build Tools

When new build tools are released, you'll need to update your Docker
image. To do this, simply build the image again:

```
$ ./create_image.sh build
```

## To Use the Build Tool via Docker

Install the aliases and functions defined in `aliases.sh` to define
versions of `bdc`, `course`, `databricks`, `gendbc` and `master_parse` that
will invoke the ones inside your Docker instance.

In your `.bashrc`, `.bash_profile` or `.zshrc` (if you use Zsh), put the
following line (with the appropriate path):

```
. /path/to/repos/build-tools/docker/aliases.sh
```
