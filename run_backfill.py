#!/usr/bin/env python3

import argparse
import os
import subprocess
import yaml

PROJ = '/Users/ctk21/proj/'
REPO = os.path.join(PROJ, 'ocaml')
BRANCH = '4.07'
SCRIPTDIR = os.path.join(PROJ, 'ctk21_bench_scripts')
OPERF_BINARY = os.path.join(PROJ, 'operf-micro/test/bin/operf-micro')
ENVIRONMENT = 'macbook'

parser = argparse.ArgumentParser(description='Build ocaml binaries and benchmarks for a backfill')
parser.add_argument('outdir', type=str, help='directory of output')
parser.add_argument('--max_hashes', type=int, help='maximum_number of hashes to process', default=1000)
parser.add_argument('--run_stages', type=str, help='stages to run', default='build,operf,upload')
parser.add_argument('--lax_mkdir', action='store_true', default=False)
parser.add_argument('--environment', type=str, default=ENVIRONMENT)
parser.add_argument('-v', '--verbose', action='store_true', default=False)

args = parser.parse_args()

def shell_exec(cmd, verbose=args.verbose, check=True, capture_output=False):
	if verbose:
		print('+ %s'%cmd)
	
	if capture_output:
		return subprocess.run(cmd, shell=True, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	else:
		return subprocess.run(cmd, shell=True, check=check)

def write_context(context, fname, verbose=args.verbose):
	s = yaml.dump(context, default_flow_style=False)
	if verbose:
		print('writing context to %s: \n%s'%(fname, s))
	print(s, file=open(fname, 'w'))


run_stages = args.run_stages.split(',')
if args.verbose: print('will run stages: %s'%run_stages)

## setup directory
outdir = os.path.abspath(args.outdir)
if args.verbose: print('making directory: %s'%outdir)
shell_exec('mkdir -p %s'%outdir, check=not args.lax_mkdir)

## generate list of hash commits
os.chdir(REPO)
shell_exec('git checkout %s'%BRANCH)
proc_output = shell_exec('git log --pretty=format:\'%%H %%s\' | grep VERSION | grep %s'%BRANCH, capture_output=True)
hash_comments = proc_output.stdout.decode('utf-8').strip().split('\n')[::-1]

#proc_output = shell_exec('git show-ref --tags | grep refs/tags/%s'%BRANCH, capture_output=True)
#hash_comments = proc_output.stdout.decode('utf-8').strip().split('\n')

hashes = [hc.split(' ')[0] for hc in hash_comments]
if args.verbose:
	for hc in hash_comments:
		print(hc)

verbose_args = ' -v' if args.verbose else ''
os.chdir(outdir)
for (n, h) in enumerate(hashes):
	if n >= args.max_hashes:
		break

	hashdir = os.path.join(outdir, h)
	if args.verbose: print('processing to %s'%hashdir)
	shell_exec('mkdir -p %s'%hashdir, check=not args.lax_mkdir)
	
	## run build for commit
	builddir = os.path.join(hashdir, 'ocaml_build')
	build_context_fname = os.path.join(builddir, 'build_context.conf')
	if 'build' in args.run_stages:
		shell_exec('%s/build_ocaml_hash.py %s %s %s'%(SCRIPTDIR, h, builddir, verbose_args))

		# output build context
		build_context = {
			'commitid': h, 
			'branch': BRANCH,
			'project': 'ocaml',
			'executable': 'vanilla', 
		}
		write_context(build_context, build_context_fname)

	## run operf for commit
	operf_micro_dir = os.path.join(hashdir, 'operf-micro')
	if 'operf' in args.run_stages:
		shell_exec('%s/run_operf_micro.py %s %s --operf_binary %s %s'%(SCRIPTDIR, os.path.join(builddir, 'bin'), operf_micro_dir, OPERF_BINARY, verbose_args))

		# output run context
		run_context = {
			'environment': args.environment, 
		}
		write_context(run_context, os.path.join(operf_micro_dir, 'run_context.conf'))
		shell_exec('cp %s %s'%(build_context_fname, os.path.join(operf_micro_dir, 'build_context.conf')))

	## upload commit
	if 'upload' in args.run_stages:
		shell_exec('%s/load_operf_data.py %s %s'%(SCRIPTDIR, operf_micro_dir, verbose_args))
