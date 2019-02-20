#!/usr/bin/env python3

import argparse
import datetime
import os
import subprocess

OPERF_BINARY = '/Users/ctk21/proj/operf-micro/test/bin/operf-micro'
BENCHMARKS = [
	'sieve',
	'lens',
	'sequence',
	'fibonnaci',
	'fft',
	'nucleic',
	'almabench',
	'format',
	]

parser = argparse.ArgumentParser(description='Run operf-micro and collate results')
parser.add_argument('bindir', type=str, help='binary directory of ocaml compiler to use')
parser.add_argument('outdir', type=str, help='output directory for results')
parser.add_argument('--operf_binary', type=str, help='operf binary to use', default=OPERF_BINARY)
parser.add_argument('-v', '--verbose', action='store_true', default=False)

args = parser.parse_args()

def shell_exec(cmd, verbose=args.verbose, check=True):
	if verbose:
		print('+ %s'%cmd)
	subprocess.run(cmd, shell=True, check=check)

# setup the directories
bindir = os.path.abspath(args.bindir)
outdir = os.path.abspath(args.outdir)

shell_exec('mkdir -p %s'%outdir)

# get git source and checkout the hash
if args.verbose: print('changing working directory to %s to run operf-micro'%outdir)
os.chdir(outdir)

tag = 'Test%s'%datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

def operf_cmd(s):
	return '%s %s'%(args.operf_binary, s)

shell_exec(operf_cmd('clean'), check=False) ## TODO: sometimes this fails, what is the correct thing to do?
shell_exec(operf_cmd('init --bin-dir %s %s'%(bindir, tag)))
shell_exec(operf_cmd('build'))

for b in BENCHMARKS:
	shell_exec(operf_cmd('run %s'%b))
	shell_exec(operf_cmd('results %s --selected %s --more-yaml > %s.summary'%(tag, b, os.path.join(outdir, b))))

