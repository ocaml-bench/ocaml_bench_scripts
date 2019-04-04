#!/usr/bin/env python3

import argparse
import datetime
import glob
import inspect
import json
import os
import pandas
import subprocess

import git_hashes
import codespeed_upload

def get_script_dir():
    return os.path.dirname(inspect.getabsfile(get_script_dir))

SCRIPTDIR = get_script_dir()
REPO = os.path.join(SCRIPTDIR, 'ocaml')
DEFAULT_BRANCH = '4.07'
DEFAULT_MAIN_BRANCH = 'trunk'
SANDMARK_REPO = os.path.join(SCRIPTDIR, 'sandmark')
SANDMARK_COMP_FMT_DEFAULT = 'https://github.com/ocaml/ocaml/archive/{tag}.tar.gz'
CODESPEED_URL = 'http://localhost:8000/'
ENVIRONMENT = 'macbook'

parser = argparse.ArgumentParser(description='Run sandmark benchmarks and upload them for a backfill')
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
parser.add_argument('--sandmark_repo', type=str, help='sandmark repo location', default=SANDMARK_REPO)
parser.add_argument('--sandmark_comp_fmt', type=str, help='sandmark location format compiler code', default=SANDMARK_COMP_FMT_DEFAULT)
parser.add_argument('--sandmark_iter', type=int, help='number of sandmark iterations', default=1)
parser.add_argument('--sandmark_pre_exec', type=str, help='benchmark pre_exec', default='')
parser.add_argument('--sandmark_no_cleanup', action='store_true', default=False)
parser.add_argument('--sandmark_tag_override', help='set the sandmark version tag manually (e.g. 4.06.1)', default=None)
parser.add_argument('--run_stages', type=str, help='stages to run', default='setup,bench,upload')
parser.add_argument('--executable_spec', type=str, help='name for executable and variant for build in "name:variant" fmt (e.g. flambda:flambda)', default='vanilla:')
parser.add_argument('--environment', type=str, help='environment tag for run (default: %s)'%ENVIRONMENT, default=ENVIRONMENT)
parser.add_argument('--upload_project_name', type=str, help='specific upload project name (default is ocaml_<branch name>', default=None)
parser.add_argument('--upload_date_tag', type=str, help='specific date tag to upload', default=None)
parser.add_argument('--codespeed_url', type=str, help='codespeed URL for upload', default=CODESPEED_URL)
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


def parse_and_format_results_for_upload(fname):
    bench_data = []
    with open(fname) as f:
        for l in f:
            raw_data = json.loads(l)
            bench_data.append({
                'name': raw_data['name'],
                'time_secs': raw_data['time_secs'],
                'user_time_secs': raw_data['user_time_secs'],
                'gc.minor_collections': raw_data['gc']['minor_collections'],
                'gc.major_collections': raw_data['gc']['major_collections'],
                'gc.compactions': raw_data['gc']['compactions'],
                })
    if not bench_data:
        print('WARN: Failed to find any data in %s'%fname)
        return []

    bench_data = pandas.DataFrame(bench_data)
    aggregated_data = bench_data.groupby('name').apply(lambda x: x.describe().T)
    aggregated_data.index.set_names(['bench_name', 'bench_metric'], inplace=True)

    upload_data = []
    for bench_name in aggregated_data.index.levels[0]:
        # TODO: how to make this configurable
        metric_name, metric_units, metric_units_title = ('time_secs', 'seconds', 'Time')

        results = aggregated_data.loc[(bench_name, 'time_secs')]
        upload_data.append({
            'commitid': h[:7],
            'commitid_long': h,
            'project': args.upload_project_name if args.upload_project_name else 'ocaml_%s'%args.branch,
            'branch': args.branch,
            'executable': executable_name,
            'executable_description': full_branch_tag,
            'environment': args.environment,
            'benchmark': bench_name,
            'units': metric_units,
            'units_title': metric_units_title,
            'result_value': results['mean'],
            'min': results['min'],
            'max': results['max'],
            'std_dev': results['std'],
            })

    return upload_data


run_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

run_stages = args.run_stages.split(',')
if args.verbose: print('will run stages: %s'%run_stages)

## setup directory
outdir = os.path.abspath(args.outdir)
if args.verbose: print('making directory: %s'%outdir)
shell_exec('mkdir -p %s'%outdir)

## generate list of hash commits
hashes = git_hashes.get_git_hashes(args)

if args.verbose:
    print('Found %d hashes using %s to do %s on'%(len(hashes), args.commit_choice_method, args.run_stages))

verbose_args = ' -v' if args.verbose else ''
os.chdir(outdir)
for h in hashes:
    hashdir = os.path.join(outdir, h)
    if args.verbose: print('processing to %s'%hashdir)
    shell_exec('mkdir -p %s'%hashdir)

    executable_name, executable_variant = args.executable_spec.split(':')

    if args.sandmark_tag_override:
        full_branch_tag = args.sandmark_tag_override
    else:
        ## TODO: we need to somehow get the '.0' more correctly
        full_branch_tag = '%s.0'%args.branch
    if executable_variant:
        full_branch_tag += '+' + executable_variant
    version_tag = os.path.join('ocaml-versions', full_branch_tag)
    sandmark_dir = os.path.join(hashdir, 'sandmark')

    if 'setup' in args.run_stages:
        if os.path.exists(sandmark_dir):
            print('Skipping sandmark setup for %s as directory there'%h)
        else:
            ## setup sandmark (make a clone and change the hash)
            shell_exec('git clone --reference %s %s %s'%(args.sandmark_repo, args.sandmark_repo, sandmark_dir))
            comp_file = os.path.join(sandmark_dir, '%s.comp'%version_tag)
            if args.verbose:
                print('writing hash information to: %s'%comp_file)
            with open(comp_file, 'w') as f:
                f.write(args.sandmark_comp_fmt.format(**{'tag': h}))

    if 'bench' in args.run_stages:
        ## run bench
        log_fname = os.path.join(hashdir, 'bench_%s.log'%run_timestamp)
        completed_proc = shell_exec_redirect('cd %s; make %s.bench ITER=%i PRE_BENCH_EXEC=%s'%(sandmark_dir, version_tag, args.sandmark_iter, args.sandmark_pre_exec), log_fname)
        if completed_proc.returncode != 0:
            print('ERROR[%d] in sandmark bench run for %s (see %s)'%(completed_proc.returncode, h, log_fname))
            ## TODO: the error isn't fatal, just that something failed in there...
            #continue

        ## move results to store them
        resultsdir = os.path.join(hashdir, 'results')
        shell_exec('mkdir -p %s'%resultsdir)
        src_file = os.path.join(sandmark_dir, '%s.bench'%version_tag)
        shell_exec('cp %s %s'%(src_file, os.path.join(resultsdir, '%s_%s'%(run_timestamp, os.path.basename(src_file)))))

        ## cleanup sandmark directory
        if not args.sandmark_no_cleanup:
            shell_exec('cd %s; make clean'%sandmark_dir)

    if 'upload' in args.run_stages:
        ## upload
        resultdir = os.path.join(hashdir, 'results')
        if args.upload_date_tag:
            fname = os.path.join(resultdir, '%s_%s.bench'%(args.upload_date_tag, full_branch_tag))
            if not os.path.exists(fname):
                print('ERROR: could not upload as could not find %s'%fname)
                continue
        else:
            glob_pat = '%s/*_%s.bench'%(resultdir, full_branch_tag)
            fnames = sorted(glob.glob(glob_pat))
            if not fnames:
                print('ERROR: could not find any results of form %s to upload'%glob_pat)
                continue

            fname = fnames[-1]

        print('Uploading data from %s'%fname)

        upload_data = parse_and_format_results_for_upload(fname)

        ## upload this stuff into the codespeed server
        if upload_data:
            codespeed_upload.post_data_to_server(args.codespeed_url, upload_data, verbose=args.verbose)

