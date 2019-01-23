# Build Tool Docker Image

## Install or update the Docker-based build tools

To install or update your Docker-based build tools, just run:

```
curl -L https://git.io/fhaLg | bash
```

If you prefer the non-shortened version, use this:

```
curl https://raw.githubusercontent.com/databricks-edu/build-tooling/master/docker/install.sh | bash
```

This command:

- Pulls down the prebuilt Docker image (`databrickseducation/build-tool`)
  from Docker Hub.
- Updates your local Docker image, if necessary.
- Pulls down the build tool aliases and installs them in
  `$HOME/.build-tools-aliases.sh`

All you have to do is ensure that Docker is installed (see below) and that
you have this command in your `.bashrc` or `.zshrc`:

```
. ~/.build-tools-aliases.sh
```

## Cleaning up "dangling" images

Over time, as you update your Docker image, you might find you're
accumulating a bunch of dangling (stale) Docker images. If you run
`docker images`, you may see a bunch with labels like `<none>`. 
_Some_ of these _might_ be stale, and stale images can consume disk space.

Consider running the following command periodically to clean things up:

```
docker rmi $(docker images -f "dangling=true" -q)
```

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
image. Currently, you have to destroy the image and rebuild it, which takes
time. (We're working on a better solution.)

To do that:

```
$ ./create_image.sh rebuild
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
