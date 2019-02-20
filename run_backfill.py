#!/usr/bin/env python3

import argparse
import datetime
import inspect
import os
import subprocess
import yaml


def get_script_dir():
 	return os.path.dirname(inspect.getabsfile(get_script_dir))

SCRIPTDIR = get_script_dir()
REPO = os.path.join(SCRIPTDIR, 'ocaml')
OPERF_BINARY = os.path.join(SCRIPTDIR, 'operf-micro/opt/bin/operf-micro')
ENVIRONMENT = 'macbook'

parser = argparse.ArgumentParser(description='Build ocaml binaries and benchmarks for a backfill')
parser.add_argument('outdir', type=str, help='directory of output')
parser.add_argument('--commit_choice_method', type=str, help='commit choice method (version, status_success, all)', default='version_tags')
parser.add_argument('--max_hashes', type=int, help='maximum_number of hashes to process', default=1000)
parser.add_argument('--run_stages', type=str, help='stages to run', default='build,operf,upload')
parser.add_argument('--environment', type=str, default=ENVIRONMENT)
parser.add_argument('--repo', type=str, help='local location of ocmal compiler repo', default=REPO)
parser.add_argument('--branch', type=str, help='git branch for the compiler', default='4.07')
parser.add_argument('--github_oauth_token', type=str, help='oauth token for github api', default=None)
parser.add_argument('-j', '--jobs', type=int, help='number of concurrent jobs during build', default=1)
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


run_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

run_stages = args.run_stages.split(',')
if args.verbose: print('will run stages: %s'%run_stages)

## setup directory
outdir = os.path.abspath(args.outdir)
if args.verbose: print('making directory: %s'%outdir)
shell_exec('mkdir -p %s'%outdir)

## generate list of hash commits
os.chdir(REPO)
shell_exec('git checkout %s'%args.branch)

if args.commit_choice_method == 'version_tags':
	proc_output = shell_exec('git log --pretty=format:\'%%H %%s\' | grep VERSION | grep %s'%args.branch, capture_output=True)
	hash_comments = proc_output.stdout.decode('utf-8').strip().split('\n')[::-1]
	
	hashes = [hc.split(' ')[0] for hc in hash_comments]
	if args.verbose:
		for hc in hash_comments:
			print(hc)

	#proc_output = shell_exec('git show-ref --tags | grep refs/tags/%s'%args.branch, capture_output=True)
	#hash_comments = proc_output.stdout.decode('utf-8').strip().split('\n')
elif args.commit_choice_method == 'status_success':
	proc_output = shell_exec('git log trunk.. --pretty=format:\'%H\'', capture_output=True)
	all_hashes = proc_output.stdout.decode('utf-8').strip().split('\n')[::-1]

	def get_hash_status(h):
		curl_xtra_args = '-s'
		if args.github_oauth_token is not None:
			curl_xtra_args = curl_xtra_args + ' -H "Authorization: token %s"'%args.github_oauth_token
		proc_output = shell_exec('curl %s https://api.github.com/repos/ocaml/ocaml/commits/%s/status | jq .state'%(curl_xtra_args, h), capture_output=True)
		return proc_output.stdout.decode('utf-8').strip().strip('"')
		
	hashes = []
	for h in all_hashes:
		state = get_hash_status(h)
		if args.verbose: print('%s is state of %s'%(state, h))
		if state == 'success':
			hashes.append(h)

elif args.commit_choice_method  == 'all':
	proc_output = shell_exec('git log trunk.. --pretty=format:\'%H\'', capture_output=True)
	hashes = proc_output.stdout.decode('utf-8').strip().split('\n')[::-1]

else:
	print('Unknown commit choice method "%s"'%args.commit_choice_method)
	sys.exit(1)


verbose_args = ' -v' if args.verbose else ''
os.chdir(outdir)
for (n, h) in enumerate(hashes):
	if n >= args.max_hashes:
		break

	hashdir = os.path.join(outdir, h)
	if args.verbose: print('processing to %s'%hashdir)
	shell_exec('mkdir -p %s'%hashdir)
	
	## run build for commit
	builddir = os.path.join(hashdir, 'ocaml_build')
	build_context_fname = os.path.join(builddir, 'build_context.conf')
	if 'build' in args.run_stages:
		log_fname = os.path.join(hashdir, 'build_%s.log'%run_timestamp) 
		shell_exec('%s/build_ocaml_hash.py --repo %s -j %d %s %s %s &> %s'%(SCRIPTDIR, args.repo, args.jobs, h, builddir, verbose_args, log_fname))

		# output build context
		build_context = {
			'commitid': h, 
			'branch': args.branch,
			'project': 'ocaml',
			'executable': 'vanilla', 
		}
		write_context(build_context, build_context_fname)

	## run operf for commit
	operf_micro_dir = os.path.join(hashdir, 'operf-micro')
	if 'operf' in args.run_stages:
		log_fname = os.path.join(hashdir, 'operf_%s.log'%run_timestamp) 
		shell_exec('%s/run_operf_micro.py %s %s --operf_binary %s %s &> %s'%(SCRIPTDIR, os.path.join(builddir, 'bin'), operf_micro_dir, OPERF_BINARY, verbose_args, log_fname))

		# output run context
		run_context = {
			'environment': args.environment, 
		}
		write_context(run_context, os.path.join(operf_micro_dir, 'run_context.conf'))
		shell_exec('cp %s %s'%(build_context_fname, os.path.join(operf_micro_dir, 'build_context.conf')))

	## upload commit
	if 'upload' in args.run_stages:
		upload_fname = os.path.join(hashdir, 'upload_%s.log'%run_timestamp) 
		shell_exec('%s/load_operf_data.py %s %s &> %s'%(SCRIPTDIR, operf_micro_dir, verbose_args, log_fname))
