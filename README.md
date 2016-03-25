#Slim-The-Filesystem-Down (`docker-stfd`)

`docker-stfd` is a tool which massively reduces the size of existing Docker images by running them, monitoring what files in the filesystem are actually being used, deleting the ones that aren't, then squashing the image. 

This will only work in the case that the *exact* same set of files are accessed each time a container is run, otherwise `docker-stfd` will not know which are safe to delete. It will also leave your container in a highly volatile state, with anything other than the original command unlikely to work.

Nevertheless, this is useful for containers which perform a straighforward deterministic calculation each time, and where size if very important. For example, we use `docker-stfd` to slim down images before sending them to the volunteers at [Cosmology@Home](https://github.com/marius311/cosmohome).

##Usage

If you would normally run your container with,
```bash
docker run <image> <cmd>
```
then,
```bash
docker-stfd <image> <cmd>
```
creates a slimmed down version (with default name `<image>-slim`).

###Notes
* If your `<cmd>` contains the same option flags as `docker-stfd`, you must use `--` to separate them, i.e. `docker-stfd <image> -- <cmd>`. 
* If running your container takes a long time, but you are sure that, e.g. within the first X seconds all of the necessary files have been accessed, a useful trick is to run `timeout X <cmd>` instead of `<cmd>`.


###Example

```bash
$ ./docker-stfd myimage:latest timeout 10 python mycode.py
Reverse engineering Dockerfile...
Inspecting container file usage...
Used files: 8054 (626M)
Unused files: 17140 (552M)
Getting base filesystem...
Creating new slimmed filesystem...
Building new container...
Created image lsplitsims:latest-slim
Uncompressed size shrunk from 644.6 MB to 211.6 MB
```

##Requirements

* Your host system needs `strace` and `docker` installed. 
* The container will needs some basic commands like `find`, `grep`, `sort`, and `readlink`. Most Debian/Ubuntu guests have this by default. This is not yet compatible with Busybox's `grep`. I have not tested others. 

##TODO
* Support for other guest distros
* Pass other docker options
* Handle images with ENTRYPOINT
* Slim at a different layer than the FROM layer
* Package up inside Docker
