#!/usr/bin/env python

from __future__ import print_function
import argparse
import os, os.path as osp
from tempfile import mkdtemp
from subprocess import check_output
from uuid import uuid4
import sys
import tarfile
import re

#the script we run inside the container to delete unused files
guest_script=r"""
#!/bin/sh

parse_strace() {  
    grep -oP "\(\".*?\"," | cut -c 3- | rev | cut -c 3- | rev | sort -u
}

get_size(){
    du -sch $1 2>/dev/null | tail -n 1 | awk '{ print $1 }'
}

# first strace the command to get all the files it uses
# then strace a readlink of all the files to resolve the entire symlink tree for all of them
used=$(/.strace -f -e trace=file $* 2>&1 | parse_strace | xargs /.strace -f -e trace=lstat readlink -f 2>&1 | parse_strace)
echo Used files: $(echo "$used" | wc -l) \($(get_size "$used")\)

# list all files and remove the used ones we've found are used
# for now, only check the usual major offenders 
unused=$(echo "$used" > /.used && find /usr /lib /var /root /sbin /bin -type f | grep -vxf /.used && rm /.used)
echo Unused files: $(echo "$unused" | wc -l) \($(get_size "$unused")\)

# delete the unused files
echo "$unused" | xargs rm -f
"""

def sh(*args,**kwargs):
    return check_output(*args,**kwargs).strip()


parser = argparse.ArgumentParser(prog='run_sim')
parser.add_argument('image')
parser.add_argument('--cmd',default='')
args = parser.parse_args()

if ':' not in args.image: args.image += ':latest'

tmpdir = mkdtemp()

#get reverse engineered Dockerfile
print("Reverse engineering Dockerfile...")

def fixline(l):
    """workaround for https://github.com/CenturyLinkLabs/dockerfile-from-image/issues/13"""
    l=re.sub(r'ENTRYPOINT &{(.*)}',r'ENTRYPOINT \1',l)
    if any([l.startswith(x) for x in ['CMD','ENTRYPOINT']]):
        l = re.sub(r'\[(.*)\]',lambda m: '[%s]'%','.join(['"%s"'%x for x in m.group(0).split('"')[1::2]]),l)
    return l

dockerfile = sh(["docker","run","--rm",
                 "-v","/var/run/docker.sock:/var/run/docker.sock",
                 "centurylink/dockerfile-from-image",args.image]).splitlines()
dockerfile = map(fixline,dockerfile)
baseimage = next(l for l in dockerfile if l.startswith('FROM')).split()[1]


#get slim'ed filesystem
print("Inspecting container file usage...")
cname = uuid4().hex
stfdfile=osp.join(tmpdir,'stfd')
with open(stfdfile,'w') as f: f.write(guest_script)
os.chmod(stfdfile,0o755)
print(sh(["docker","run","--name",cname,"--privileged",
    "-v",sh(["which","strace"]).strip()+":/.strace",
    "-v",stfdfile+":/stfd",
    "--entrypoint","sh",args.image,"-c",'/stfd %s'%args.cmd]))
sh(["docker","export","-o",osp.join(tmpdir,"slim.tar"),cname])
sh(["docker","rm",cname])


#get base filesystem
print("Getting base filesystem...")
cname = uuid4().hex
sh(["docker","run","--name",cname,"--entrypoint","sh",baseimage,"-c","true"])
sh(["docker","export","-o",osp.join(tmpdir,"base.tar"),cname])
sh(["docker","rm",cname])

#create tar with files in slim not already in base
print("Creating new slimmed filesystem...")
os.makedirs(osp.join(tmpdir,"build"))
with tarfile.open(osp.join(tmpdir,"base.tar")) as base:
    with tarfile.open(osp.join(tmpdir,"slim.tar")) as slim:
        with tarfile.open(osp.join(tmpdir,"build","rootfs.tar"),'w') as rootfs:
            for m in slim.getmembers():
                if (m.name not in base.getnames()):
                    rootfs.addfile(m,slim.extractfile(m) if m.isfile() else None)
                else:
                    #TODO: diff file
                    pass

#build new container
print("Building new container...")
dockerfile = [l for l in dockerfile if not any([l.startswith(x) for x in ['COPY','ADD','RUN']])]
dockerfile += ['ADD rootfs.tar /']
newimage = args.image+'-slim'
with open(osp.join(tmpdir,"build","Dockerfile"),'w') as df:  df.write('\n'.join(dockerfile))
sh(["docker","build","-t",newimage,osp.join(tmpdir,"build")])

#cleanup
sh(["rm","-rf",tmpdir])

def get_size(image):
    return sh(["docker","images","--format","{{.Size}}",image])
print("Created image "+newimage)
print("Uncompressed size shrunk from %s to %s"%(get_size(args.image),get_size(newimage)))