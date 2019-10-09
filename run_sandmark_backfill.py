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
SANDMARK_RUN_BENCH_TARGETS_DEFAULT = 'run_orun'
CODESPEED_URL = 'http://localhost:8000/'
ENVIRONMENT = 'macbook'

parser = argparse.ArgumentParser(description='Run sandmark benchmarks and upload them for a backfill')
parser.add_argument('outdir', type=str, help='directory of output')
parser.add_argument('--repo', type=str, help='local location of ocmal compiler repo (default: %s)'%REPO, default=REPO)
parser.add_argument('--branch', type=str, help='git branch for the compiler (default: %s)'%DEFAULT_BRANCH, default=DEFAULT_BRANCH)
parser.add_argument('--main_branch', type=str, help='name of mainline git branch for compiler (default: %s)'%DEFAULT_MAIN_BRANCH, default=DEFAULT_MAIN_BRANCH)
parser.add_argument('--repo_pull', action='store_true', help="do a pull on the git repo before selecting hashes", default=False)
parser.add_argument('--repo_reset_hard', action='store_true', help="after pulling a branch, reset it hard to the origin. Can need this for remote branches where they have been force pushed", default=False)
parser.add_argument('--use_repo_reference', action='store_true', help="use reference to clone a local git repo", default=False)
parser.add_argument('--no_first_parent', action='store_true', help="By default we use first-parent on git logs (to keep date ordering sane); this option turns it off", default=False)
parser.add_argument('--commit_choice_method', type=str, help='commit choice method (version_tags, status_success, hash=XXX, delay=00:05:00, all)', default='version_tags')
parser.add_argument('--commit_after', type=str, help='select commits after the specified date (e.g. 2017-10-02)', default=None)
parser.add_argument('--commit_before', type=str, help='select commits before the specified date (e.g. 2017-10-02)', default=None)
parser.add_argument('--github_oauth_token', type=str, help='oauth token for github api', default=None)
parser.add_argument('--max_hashes', type=int, help='maximum_number of hashes to process', default=1000)
parser.add_argument('--incremental_hashes', action='store_true', default=False)
parser.add_argument('--sandmark_repo', type=str, help='sandmark repo location', default=SANDMARK_REPO)
parser.add_argument('--sandmark_comp_fmt', type=str, help='sandmark location format compiler code', default=SANDMARK_COMP_FMT_DEFAULT)
parser.add_argument('--sandmark_iter', type=int, help='number of sandmark iterations', default=1)
parser.add_argument('--sandmark_pre_exec', type=str, help='benchmark pre_exec', default='')
parser.add_argument('--sandmark_no_cleanup', action='store_true', default=False)
parser.add_argument('--sandmark_tag_override', help='set the sandmark version tag manually (e.g. 4.06.1)', default=None)
parser.add_argument('--sandmark_run_bench_targets', type=str, help='comma seperated list of RUN_BENCH_TARGET arguments to run in sandmark', default=SANDMARK_RUN_BENCH_TARGETS_DEFAULT)
parser.add_argument('--run_stages', type=str, help='stages to run (setup,bench,archive,upload)', default='setup,bench,upload')
parser.add_argument('--executable_spec', type=str, help='name for executable and variant for build in "name:variant" fmt (e.g. flambda:flambda)', default='vanilla:')
parser.add_argument('--environment', type=str, help='environment tag for run (default: %s)'%ENVIRONMENT, default=ENVIRONMENT)
parser.add_argument('--archive_dir', type=str, help='location to make archive (comma seperated list)', default='')
parser.add_argument('--upload_project_name', type=str, help='specific upload project name (default is ocaml_<branch name>', default=None)
parser.add_argument('--upload_date_tag', type=str, help='specific date tag to upload', default=None)
parser.add_argument('--codespeed_url', type=str, help='codespeed URL for upload', default=CODESPEED_URL)
parser.add_argument('-v', '--verbose', action='store_true', default=False)

args = parser.parse_args()

upload_project_name = args.upload_project_name if args.upload_project_name else 'ocaml_%s'%args.branch

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

def use_bench_result_dirs_to_determine_timestamp(resultdir):
    resultdir_candidates = sorted(glob.glob(os.path.join(resultdir, '[0-9]'*8+'_'+'[0-9]'*6)))
    if len(resultdir_candidates) == 0:
        print('ERROR: could not find bench logfile for run timestamp (resultdir=%s)'%resultdir)
        return None

    d = resultdir_candidates[-1]
    if len(resultdir_candidates) > 1:
        print('WARN: more than one logfile candidate for timestamp, so took last %s'%d)

    return d, os.path.basename(d.rstrip('/'))

def parse_and_format_results_for_upload(fname, artifacts_timestamp):
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
                'gc.compactions': raw_data['gc'].get('compactions', 0),
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
            'project': upload_project_name,
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
            'metadata': {'artifacts_location': '%s/%s__%s/%s/%s/%s/%s/'%(args.environment, upload_project_name, args.branch, h, executable_name, artifacts_timestamp, bench_name)},
            })

    return upload_data


run_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

run_stages = args.run_stages.split(',')
if args.verbose: print('will run stages: %s'%run_stages)

## setup directory
outdir = os.path.abspath(args.outdir)
if args.verbose: print('making directory: %s'%outdir)
shell_exec('mkdir -p %s'%outdir)

archive_dirs = [] if args.archive_dir == '' else args.archive_dir.split(',')
archive_dirs = [os.path.abspath(f) for f in archive_dirs]
def check_archive_dir(d):
    if not os.path.exists(d):
        print('ERROR: can only archive to existing locations: %s'%d)
        return False
    return True
archive_dirs = [f for f in archive_dirs if check_archive_dir(f)]

## generate list of hash commits
hashes = git_hashes.get_git_hashes(args)

if args.incremental_hashes:
    def check_hash_new(h):
        hash_dir = os.path.join(outdir, h)
        hash_already_run = os.path.exists(hash_dir)
        if args.verbose and hash_already_run:
            print('Found results at %s skipping rerun'%hash_dir)
        return not hash_already_run

    hashes = [h for h in hashes if check_hash_new(h)]

hashes = hashes[-args.max_hashes:]

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
    sandmark_results_dir = os.path.join(sandmark_dir, '_results')
    resultsdir = os.path.join(hashdir, 'results')

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
        src_dir = os.path.join(sandmark_results_dir, full_branch_tag)
        dest_dir = os.path.join(resultsdir, run_timestamp)
        shell_exec('mkdir -p %s'%dest_dir)

        targets = args.sandmark_run_bench_targets.split(',')
        for target in targets:
            if args.verbose:
                print('Running bench target %s'%target)

            log_fname = os.path.join(hashdir, '%s_%s.log'%(run_timestamp, target))
            completed_proc = shell_exec_redirect('cd %s; make %s.bench ITER=%i PRE_BENCH_EXEC=%s RUN_BENCH_TARGET=%s'%(sandmark_dir, version_tag, args.sandmark_iter, args.sandmark_pre_exec, target), log_fname)
            if completed_proc.returncode != 0:
                print('ERROR[%d] in sandmark bench run for %s (see %s)'%(completed_proc.returncode, h, log_fname))
                ## TODO: the error isn't fatal, just that something failed in there...
                #continue

            ## put the logfile into the right result directory
            shell_exec('cp %s %s/'%(log_fname, dest_dir))

        ## copy all result artifacts
        shell_exec('cp -r %s/ %s/'%(src_dir, dest_dir))

        ## cleanup sandmark directory
        if not args.sandmark_no_cleanup:
            shell_exec('cd %s; make clean'%sandmark_dir)

    if 'archive' in args.run_stages:
        if len(archive_dirs) == 0:
            print('WARN: no archive_dirs to run on (is the --archive_dir argument set?)')
        else:
            for archive_dir in archive_dirs:
                ## figure the archive timestamp
                archive_logdir, archive_timestamp = use_bench_result_dirs_to_determine_timestamp(resultsdir)

                archive_path = os.path.join(
                    archive_dir,
                    args.environment, ## environment (often hostname)
                    upload_project_name + '__' + args.branch, ## project name and branch (identifies github repo)
                    h, ## commit hash
                    executable_name, ## name of the executable variant (e.g. vanilla, flambda)
                    archive_timestamp ## timestamp fo the run
                    )

                if args.verbose:
                    print('writing archive to: %s'%archive_path)

                ## archive the data
                shell_exec('mkdir -p %s'%archive_path)
                shell_exec('cp -r %s/*.log %s'%(archive_logdir, archive_path))
                shell_exec('cp -r %s/* %s'%(os.path.join(archive_logdir, full_branch_tag), archive_path))

    if 'upload' in args.run_stages:
        if not 'run_orun' in args.sandmark_run_bench_targets.split(','):
            print('WARN: not running upload as run_orun not found in sandmark_run_bench_targets')
            continue

        ## upload
        resultdir = os.path.join(hashdir, 'results')
        if args.upload_date_tag:
            upload_timestamp = args.upload_date_tag
            upload_dir = os.path.join(resultsdir, upload_timestamp)
        else:
            ## figure the upload timestamp
            upload_dir, upload_timestamp = use_bench_result_dirs_to_determine_timestamp(resultsdir)

        fname = os.path.join(upload_dir, full_branch_tag, '%s.orun.bench'%full_branch_tag)
        if not os.path.exists(fname):
            print('ERROR: could not upload as could not find %s'%fname)
            continue

        print('Uploading data from %s'%fname)

        upload_data = parse_and_format_results_for_upload(fname, upload_timestamp)

        ## upload this stuff into the codespeed server
        if upload_data:
            codespeed_upload.post_data_to_server(args.codespeed_url, upload_data, verbose=args.verbose)

