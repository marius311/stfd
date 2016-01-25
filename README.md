#Slim-The-Filesystem-Down (`stfd`)

**Warning: alpha software, use at own risk**

`stfd` is a tool which massively reduces the size of existing Docker images by running them, monitoring what files in the filesystem are actually being used, deleting the ones that aren't, then [squashing](https://github.com/jwilder/docker-squash) the image. 

This will only work in the case that the *exact* same set of files are accessed each time a container is run, otherwise `stfd` will not know which are safe to delete. It will also leave your container in a highly volatile state, with anything other than the original command unlikely to work.

Nevertheless, this is useful for containers which perform a straighforward deterministic calculation each time, and where size if very important. For example, we use `stfd` to slim down images before sending them to the volunteers at [Cosmology@Home](https://github.com/marius311/cosmohome).

##Usage

If you would normally run your container with,
```bash
docker run <args> <tag> <cmd>
```
then do (quotes necessary if spaces are present), 
```bash
sudo ./stfd "<args>" "<tag>" "<cmd>"
```
This will run the container, create a slimmed down version with the name `<tag>-slim`, and `docker-squash` it. 

###Notes
* If running your container takes a long time, but you are sure say within the first few seconds all of the necessary files have been accessed, a useful trick is to run e.g. `timeout 10 <cmd>` instead of `<cmd>`.
* `stfd` doesn't know about volumes, so if any volumes are mounted in the container, files from inside them may be deleted.


###Example

```bash
$ sudo ./stfd "" myimage:latest "timeout 10 python mycode.py"
Used files: 8800 (639M)
Unused files: 16170 (477M)
Squashing...
Done. Test with:
docker run myimage:latest-slim timeout 10 python mycode.py
```

##Requirements

* Your host system needs `strace` and [`docker-squash`](https://github.com/jwilder/docker-squash) installed. 
* The container will needs some basic commands like `find`, `grep`, `sort`, and `readlink`. Most Debian/Ubuntu guests have this by default. This is not yet compatible with Busybox's `grep`. I have not tested others. 

##TODO
* Support for other guest distros
* Nicer command line options
* Ability to pass options to `docker-squash`
