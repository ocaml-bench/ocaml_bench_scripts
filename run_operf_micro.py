#!/usr/bin/env python3

import argparse
import datetime
import glob
import os
import subprocess

OPERF_BINARY = '/Users/ctk21/proj/operf-micro/test/bin/operf-micro'
BENCHMARKS = [
	'almabench',
	'nucleic',
	'boyer', ## TODO: need a way to tag this as 'long'
	'kb', ## TODO: need a way to tag this as 'long'
	'num_analysis', ## TODO: need a way to tag this as 'long'
	'bigarray_rev',
	'fibonnaci',
	'lens',
	##'vector_functor', NB: not obvious this one is doing enough to be sensible to run
	'kahan_sum',
	'hamming', ## TODO: need a way to tag this as 'long'
	'sieve',
	'list',
	'format',
	'fft',
	'bdd',
	'sequence',
	'nullable_array',
	]
DEFAULT_TIME_QUOTA = 5.0

## TODO: make time quotas a lookup for: Short, Long, Longer
## TODO: make benchmarks a lookup of the type: 'almabench' -> {'Short'}
## TODO: how to specify these through the command line... almabench:Short,nucleic:Long,...

parser = argparse.ArgumentParser(description='Run operf-micro and collate results')
parser.add_argument('bindir', type=str, help='binary directory of ocaml compiler to use')
parser.add_argument('outdir', type=str, help='output directory for results')
parser.add_argument('--results_timestamp', type=str, help='explicit timestamp to use', default=datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
parser.add_argument('--benchmarks', type=str, help='comma seperated list of benchmarks to run', default=','.join(BENCHMARKS))
parser.add_argument('--use_addr_no_randomize', action='store_true', help='Use addr_no_randomize option when running the benchmarks (Linux only)', default=False)
parser.add_argument('--time_quota', help='time_quota for operf-micro (default: %s)'%DEFAULT_TIME_QUOTA, default=DEFAULT_TIME_QUOTA)
parser.add_argument('--operf_binary', type=str, help='operf binary to use', default=OPERF_BINARY)
parser.add_argument('--make_plots', action='store_true', help='create png plots', default=False)
parser.add_argument('--no_clean', action='store_true', help='don\'t cleanup the .operf directories after running', default=False)
parser.add_argument('-v', '--verbose', action='store_true', default=False)

args = parser.parse_args()

def shell_exec(cmd, verbose=args.verbose, check=True):
	if verbose:
		print('+ %s'%cmd)
	subprocess.run(cmd, shell=True, check=check)

# setup the directories
bindir = os.path.abspath(args.bindir)
outdir = os.path.abspath(args.outdir)
resultdir = os.path.join(outdir, args.results_timestamp)

shell_exec('mkdir -p %s'%resultdir)

# get git source and checkout the hash
if args.verbose: print('changing working directory to %s to run operf-micro'%resultdir)
os.chdir(resultdir)

tag = 'Test%s'%datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

def operf_cmd(s):
	return '%s %s'%(args.operf_binary, s)

## NB: can't use the 'operf-micro run' -o option because the result files will
##     then not be visible to the 'operf-micro results' command that follows
def copy_out_results(tag, benchmark, resultdir):
	operf_results_tag_dir = os.path.join(os.path.expanduser('~'), '.operf', 'micro', tag, '*')
	all_run_dirs = sorted(glob.glob(operf_results_tag_dir))
	if len(all_run_dirs) > 0:
		run_dir = all_run_dirs[-1]
		shell_exec('cp %s %s'%(os.path.join(run_dir, '%s.result'%benchmark), resultdir), check=False)
	else:
		print('ERROR: failed to find runs in %s'%operf_results_tag_dir)


shell_exec(operf_cmd('init --bin-dir %s %s'%(bindir, tag)))
shell_exec(operf_cmd('build'))

for b in args.benchmarks.split(','):
	try:
		print('%s: running %s'%(str(datetime.datetime.now()), b))
		no_randomize_prefix = 'setarch `uname -m` --addr-no-randomize ' if args.use_addr_no_randomize else ''
		shell_exec(no_randomize_prefix+operf_cmd('run --time-quota %s %s'%(args.time_quota, b)))
		copy_out_results(tag, b, resultdir)
		shell_exec(operf_cmd('results %s --selected %s --more-yaml > %s.summary'%(tag, b, os.path.join(resultdir, b))))
		if args.make_plots:
			shell_exec(operf_cmd('plot --png %s %s'%(b, tag)))
			plotdir = os.path.join(resultdir, 'plot')
			shell_exec('mkdir -p %s && mv %s/.operf/micro/plot/*.png %s'%(plotdir, resultdir, plotdir))
	except Exception as e:
		print('ERROR: operf run failed for %s'%b)
		print(e)

if not args.no_clean:
	shell_exec(operf_cmd('clean'), check=False)
	shell_exec('rm -rf %s'%os.path.join(os.path.expanduser('~'), '.operf', 'micro', tag))
