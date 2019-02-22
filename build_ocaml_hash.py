#!/usr/bin/env python3 -u

import argparse
import os
import subprocess

REPO='https://github.com/ocaml/ocaml'

parser = argparse.ArgumentParser(description='Build a given ocaml compiler repo hash')
parser.add_argument('hash', type=str, help='commit hash to pull')
parser.add_argument('basedir', type=str, help='location to put the source and the build')
parser.add_argument('--configure_args', type=str, help='additional configure arguments', default=None)
parser.add_argument('--repo', type=str, help='alternate URL for the repo', default=REPO)
parser.add_argument('-j', '--jobs', type=int, help='number of jobs for make in build', default=1)
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
xtra_args = "" if args.configure_args is None else args.configure_args
shell_exec('./configure --prefix %s %s'%(basedir, xtra_args))
shell_exec('make world -j %d'%args.jobs)
shell_exec('make world.opt -j %d'%args.jobs)
shell_exec('make install')

