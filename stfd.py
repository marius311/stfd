#!/usr/bin/env python

import argparse
import os, os.path as osp
from tempfile import mkdtemp
from subprocess import check_output
from uuid import uuid4
import sys
import tarfile

def sh(*args,**kwargs):
    return check_output(*args,**kwargs).strip()


parser = argparse.ArgumentParser(prog='run_sim')
parser.add_argument('image')
parser.add_argument('--cmd',default='')
args = parser.parse_args()

if ':' not in args.image: args.image += ':latest'

tmpdir = mkdtemp()

#get reverse engineered Dockerfile
print "Reverse engineering Dockerfile..."
dockerfile = sh(["docker","run","--rm",
                          "-v","/var/run/docker.sock:/var/run/docker.sock",
                           "centurylink/dockerfile-from-image",args.image]).splitlines()
baseimage = (l for l in dockerfile if l.startswith('FROM')).next().split()[1]


#get slim'ed filesystem
print "Inspecting container file usage..."
cname = uuid4().hex
print sh(["docker","run","--name",cname,"--privileged",
    "-v",sh(["which","strace"]).strip()+":/.strace",
    "-v",osp.join(osp.abspath(osp.dirname(__file__)),"stfd.guest")+":/stfd",
    "--entrypoint","sh",args.image,"-c",'/stfd %s'%args.cmd])
sh(["docker","export","-o",osp.join(tmpdir,"slim.tar"),cname])
sh(["docker","rm",cname])


#get base filesystem
print "Getting base filesystem..."
cname = uuid4().hex
sh(["docker","run","--name",cname,"--entrypoint","sh",baseimage,"-c","true"])
sh(["docker","export","-o",osp.join(tmpdir,"base.tar"),cname])
sh(["docker","rm",cname])

#create tar with files in slim not already in base
print "Creating new slimmed filesystem..."
os.makedirs(osp.join(tmpdir,"build"))
with tarfile.open(osp.join(tmpdir,"base.tar")) as base:
    with tarfile.open(osp.join(tmpdir,"slim.tar")) as slim:
        with tarfile.open(osp.join(tmpdir,"build","rootfs.tar"),'w') as rootfs:
            for m in slim.getmembers():
                #TODO: diff file, also, add links
                if m.isfile() and (m.name not in base.getnames()): 
                    rootfs.addfile(m,slim.extractfile(m))


#build new container
print "Building new container..."
dockerfile = [l for l in dockerfile if not any([l.startswith(x) for x in ['COPY','ADD','RUN']])]
dockerfile += ['ADD rootfs.tar /']
newimage = args.image+'-slim'
with open(osp.join(tmpdir,"build","Dockerfile"),'w') as df:  df.write('\n'.join(dockerfile))
sh(["docker","build","-t",newimage,osp.join(tmpdir,"build")])

#cleanup
sh(["rm","-rf",tmpdir])

def get_size(image):
    return sh(["docker","images","--format","{{.Size}}",image])
print "Created image "+newimage
print "Uncompressed size shrunk from %s to %s"%(get_size(args.image),get_size(newimage))
