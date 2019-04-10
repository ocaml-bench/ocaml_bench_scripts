#!/usr/bin/env python3

import argparse
import datetime
import inspect
import os
import subprocess
import yaml

import git_hashes

def get_script_dir():
 	return os.path.dirname(inspect.getabsfile(get_script_dir))

SCRIPTDIR = get_script_dir()
REPO = os.path.join(SCRIPTDIR, 'ocaml')
DEFAULT_BRANCH = '4.07'
DEFAULT_MAIN_BRANCH = 'trunk'
OPERF_BINARY = os.path.join(SCRIPTDIR, 'operf-micro/opt/bin/operf-micro')
CODESPEED_URL = 'http://localhost:8000/'
ENVIRONMENT = 'macbook'

parser = argparse.ArgumentParser(description='Build ocaml binaries, benchmarks and upload them for a backfill')
parser.add_argument('outdir', type=str, help='directory of output')
parser.add_argument('--repo', type=str, help='local location of ocmal compiler repo (default: %s)'%REPO, default=REPO)
parser.add_argument('--branch', type=str, help='git branch for the compiler (default: %s)'%DEFAULT_BRANCH, default=DEFAULT_BRANCH)
parser.add_argument('--main_branch', type=str, help='name of mainline git branch for compiler (default: %s)'%DEFAULT_MAIN_BRANCH, default=DEFAULT_MAIN_BRANCH)
parser.add_argument('--repo_pull', action='store_true', help="do a pull on the git repo before selecting hashes", default=False)
parser.add_argument('--use_repo_reference', action='store_true', help="use reference to clone a local git repo", default=False)
parser.add_argument('--no_first_parent', action='store_true', help="By default we use first-parent on git logs (to keep date ordering sane); this option turns it off", default=False)
parser.add_argument('--commit_choice_method', type=str, help='commit choice method (version_tags, status_success, hash=XXX, delay=00:05:00, all)', default='version_tags')
parser.add_argument('--commit_after', type=str, help='select commits after the specified date (e.g. 2017-10-02)', default=None)
parser.add_argument('--commit_before', type=str, help='select commits before the specified date (e.g. 2017-10-02)', default=None)
parser.add_argument('--github_oauth_token', type=str, help='oauth token for github api', default=None)
parser.add_argument('--max_hashes', type=int, help='maximum_number of hashes to process', default=1000)
parser.add_argument('--run_stages', type=str, help='stages to run', default='build,operf,upload')
parser.add_argument('--executable_spec', type=str, help='name for executable and configure_args for build in "name:configure_args" fmt (e.g. flambda:--enable_flambda)', default='vanilla:')
parser.add_argument('--use_addr_no_randomize', action='store_true', help='use addr_no_randomize to run the operf benchmarks (Linux only)', default=False)
parser.add_argument('--rerun_operf', action='store_true', help='regenerate operf results with rerun if already present', default=False)
parser.add_argument('--no_operf_cleanup', action='store_true', help='don\'t cleanup the operf results', default=False)
parser.add_argument('--environment', type=str, help='environment tag for run (default: %s)'%ENVIRONMENT, default=ENVIRONMENT)
parser.add_argument('--upload_project_name', type=str, help='specific upload project name (default is ocaml_<branch name>', default=None)
parser.add_argument('--upload_date_tag', type=str, help='specific date tag to upload', default=None)
parser.add_argument('--codespeed_url', type=str, help='codespeed URL for upload', default=CODESPEED_URL)
parser.add_argument('-j', '--jobs', type=int, help='number of concurrent jobs during build', default=1)
parser.add_argument('-v', '--verbose', action='store_true', default=False)

args = parser.parse_args()

def shell_exec(cmd, verbose=args.verbose, check=False, stdout=None, stderr=None):
	if verbose:
		print('+ %s'%cmd)
	return subprocess.run(cmd, shell=True, check=check, stdout=stdout, stderr=stderr)


def shell_exec_redirect(cmd, fname, verbose=args.verbose, check=False):
	if verbose:
		print('+ %s'%cmd)
		print('+ with stdout/stderr -> %s'% fname)
	with open(fname, 'w') as f:
		return shell_exec(cmd, verbose=False, check=check, stdout=f, stderr=subprocess.STDOUT)


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
hashes = git_hashes.get_git_hashes(args)
repo_path = os.path.abspath(args.repo)

if args.verbose:
	print('Found %d hashes using %s to do %s on'%(len(hashes), args.commit_choice_method, args.run_stages))

verbose_args = ' -v' if args.verbose else ''
os.chdir(outdir)
for h in hashes:
	hashdir = os.path.join(outdir, h)
	if args.verbose: print('processing to %s'%hashdir)
	shell_exec('mkdir -p %s'%hashdir)

	## run build for commit
	builddir = os.path.join(hashdir, 'ocaml_build')
	build_context_fname = os.path.join(builddir, 'build_context.conf')
	if 'build' in args.run_stages:
		executable_name, configure_args = args.executable_spec.split(':')

		if os.path.isfile(os.path.join(builddir, 'bin', 'ocaml')):
			print('Skipping build for %s as already built'%h)
		else:
			log_fname = os.path.join(hashdir, 'build_%s.log'%run_timestamp)
			use_reference_opt = '--use_reference' if args.use_repo_reference else ''
			completed_proc = shell_exec_redirect('%s/build_ocaml_hash.py --repo %s %s -j %d --configure_args="%s" %s %s %s'%(SCRIPTDIR, repo_path, use_reference_opt, args.jobs, configure_args, verbose_args, h, builddir), log_fname)
			if completed_proc.returncode != 0:
				print('ERROR[%d] in build_ocaml_hash for %s (see %s)'%(completed_proc.returncode, h, log_fname))
				continue

			# output build context
			build_context = {
				'commitid': h[:7],
				'commitid_long': h,
				'branch': args.branch,
				'project': args.upload_project_name if args.upload_project_name else 'ocaml_%s'%args.branch,
				'executable': executable_name,
				'executable_description': './configure %s'%configure_args,
			}
			write_context(build_context, build_context_fname)

	## run operf for commit
	operf_micro_dir = os.path.join(hashdir, 'operf-micro')
	if 'operf' in args.run_stages:
		if args.rerun_operf or not os.path.exists(operf_micro_dir) or not os.listdir(operf_micro_dir):
			log_fname = os.path.join(hashdir, 'operf_%s.log'%run_timestamp)
			use_addr_no_randomize_opt = '--use_addr_no_randomize' if args.use_addr_no_randomize else ''
			no_operf_cleanup_opt = '--no_clean' if args.no_operf_cleanup else ''
			completed_proc = shell_exec_redirect('%s/run_operf_micro.py --make_plots --results_timestamp %s --operf_binary %s %s %s %s %s %s'%(SCRIPTDIR, run_timestamp, OPERF_BINARY, use_addr_no_randomize_opt, no_operf_cleanup_opt, verbose_args, os.path.join(builddir, 'bin'), operf_micro_dir), log_fname)
			if completed_proc.returncode != 0:
				print('ERROR[%d] in run_operf_micro for %s (see %s)'%(completed_proc.returncode, h, log_fname))
				continue

			# output run context
			run_context = {
				'environment': args.environment,
			}

			resultdir = os.path.join(operf_micro_dir, run_timestamp)
			write_context(run_context, os.path.join(resultdir, 'run_context.conf'))
			shell_exec('cp %s %s'%(build_context_fname, os.path.join(resultdir, 'build_context.conf')))
		else:
			print('Skipping operf run for %s as already have results %s'%(h, os.listdir(operf_micro_dir)))

	## upload commit
	if 'upload' in args.run_stages:
		log_fname = os.path.join(hashdir, 'upload_%s.log'%run_timestamp)

		if args.upload_date_tag:
			resultdir = args.upload_date_tag
		else:
			result_dirs = sorted(os.listdir(operf_micro_dir)) if os.path.exists(operf_micro_dir) else []
			resultdir = result_dirs[-1] if result_dirs else None

		if resultdir:
			resultdir = os.path.join(operf_micro_dir, resultdir)
			print('uploading results from %s'%resultdir)

			completed_proc = shell_exec_redirect('%s/load_operf_data.py --codespeed_url %s %s %s'%(SCRIPTDIR, args.codespeed_url, verbose_args, resultdir), log_fname)
			if completed_proc.returncode != 0:
				print('ERROR[%d] in load_operf_data for %s (see %s)'%(completed_proc.returncode, h, log_fname))
				continue
		else:
			print("ERROR couldn't find any result directories to upload in %s"%operf_micro_dir)
