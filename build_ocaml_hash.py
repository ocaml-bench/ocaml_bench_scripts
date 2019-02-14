#!/usr/bin/env python3

import argparse
import os
import subprocess

#REPO='https://github.com/ocaml/ocaml'
REPO='file:///Users/ctk21/proj/ocaml_repo_clean/'

parser = argparse.ArgumentParser(description='Build a given ocaml compiler repo hash')
parser.add_argument('hash', type=str, help='commit hash to pull')
parser.add_argument('basedir', type=str, help='location to put the source and the build')
parser.add_argument('--repo', type=str, help='alternate URL for the repo', default=REPO)
parser.add_argument('-v', '--verbose', action='store_true', default=False)

args = parser.parse_args()

def shell_exec(cmd, verbose=args.verbose, check=True):
	if verbose:
		print('+ %s'%cmd)
	subprocess.run(cmd, shell=True, check=check)

# setup the directories
basedir = os.path.abspath(args.basedir)

if args.verbose: print('making directory: %s'%basedir)
os.mkdir(basedir)
srcdir = os.path.join(basedir, 'src')

if args.verbose: print('making directory: %s'%basedir)
os.mkdir(srcdir)

# get git source and checkout the hash
shell_exec('git clone %s %s'%(args.repo, srcdir))

os.chdir(srcdir)

shell_exec('git checkout %s'%args.hash)

# build the source
shell_exec('./configure --prefix %s'%basedir)
shell_exec('make world')
shell_exec('make world.opt')
shell_exec('make install')

