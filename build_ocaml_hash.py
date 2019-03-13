#!/usr/bin/env python3

import argparse
import os
import subprocess

REPO='https://github.com/ocaml/ocaml'

parser = argparse.ArgumentParser(description='Build a given ocaml compiler repo hash')
parser.add_argument('hash', type=str, help='commit hash to pull')
parser.add_argument('basedir', type=str, help='location to put the source and the build')
parser.add_argument('--configure_args', type=str, help='additional configure arguments', default=None)
parser.add_argument('--repo', type=str, help='alternate URL for the repo', default=REPO)
parser.add_argument('--use_reference', action='store_true', help='use reference to clone the source (only works on local repos)', default=False)
parser.add_argument('--no_clean', action='store_true', default=False)
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


if args.use_reference:
	shell_exec('git clone --reference %s %s %s'%(args.repo, args.repo, srcdir))
else:
	shell_exec('git clone %s %s'%(args.repo, srcdir))

os.chdir(srcdir)
shell_exec('git checkout %s'%args.hash)
shell_exec('git clean -f -d -x')

# build the source
xtra_args = "" if args.configure_args is None else args.configure_args
shell_exec('./configure --prefix %s %s'%(basedir, xtra_args))
shell_exec('make world -j %d'%args.jobs)
shell_exec('make world.opt -j %d'%args.jobs)
shell_exec('make install')
if not args.no_clean:
	shell_exec('make clean')
