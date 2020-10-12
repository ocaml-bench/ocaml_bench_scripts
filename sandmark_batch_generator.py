#!/usr/bin/env python3

import argparse
import datetime
import glob
import inspect
import os
import subprocess
import yaml

from collections import defaultdict
class SafeDict(dict):
    def __missing__(self, key):
        return ''

def get_script_dir():
    return os.path.dirname(inspect.getabsfile(get_script_dir))

SCRIPTDIR = get_script_dir()

parser = argparse.ArgumentParser(description='Convert a batch config to a collection of run scripts')
parser.add_argument('config', type=str, help='config file' )
parser.add_argument('outdir', type=str, help='directory of output')
parser.add_argument('-v', '--verbose', action='store_true', default=False)

args = parser.parse_args()

SCRIPT_PREAMBLE = '''#!/bin/sh

# don't allow unset variables
set -o nounset

# be verbose as we execute
set -x

TIMESTAMP=`date +'%Y%m%d_%H%M%S'`

# make sure python log files are in order
export PYTHONUNBUFFERED=true

'''

SCRIPT_PARAMS = '''
SCRIPTDIR={scriptdir}
SCRATCHDIR={scratchdir}

BENCH_TARGETS={bench_targets}
BENCH_CORE={bench_core}
BUILD_BENCH_TARGET={build_bench_target}
ENVIRONMENT={environment}
EXEC_SPEC={exec_spec}
CODESPEED_URL={codespeed_url}
CODESPEED_DB={ocamlspeed_dir}/data/data.db
RUN_JSON={run_json}
ARCHIVE_DIR={ocamlspeed_dir}/artifacts/

GITHUB_USER={github_user}
GITHUB_REPO={github_repo}
BRANCH={branch}
FIRST_COMMIT={first_commit}
MAX_HASHES={max_hashes}
OCAML_VERSION={ocaml_version}
RUN_PATH_TAG={run_path_tag}
CONFIGURE_OPTIONS="{configure_options}"
OCAMLRUNPARAM="{ocamlrunparam}"
CODESPEED_NAME={codespeed_name}

'''

SCRIPT_BODY = '''
RUNDIR=${SCRATCHDIR}/${RUN_PATH_TAG}

RUN_STAGES=setup,bench,archive,upload


# needed to get the path to include a dune binary
# NB: a full eval $(opam config env) breaks the sandmark build in a strange way...
eval $(opam config env | grep ^PATH=)

mkdir -p ${ARCHIVE_DIR}

## STAGES:
##  - get local copy of git repo
##  - setup target codespeed db to see project
##  - run backfill script to do it


cd $SCRIPTDIR

## get local copy of git repo
REPO=${GITHUB_USER}__${GITHUB_REPO}
if [ ! -d ${REPO} ]; then
	git clone https://github.com/${GITHUB_USER}/${GITHUB_REPO}.git ${REPO}
fi

## setup target codespeed db to see project
sqlite3 ${CODESPEED_DB} "INSERT INTO codespeed_project (name,repo_type,repo_path,repo_user,repo_pass,commit_browsing_url,track,default_branch) SELECT '${CODESPEED_NAME}', 'G', 'https://github.com/${GITHUB_USER}/${GITHUB_REPO}', '${GITHUB_USER}', '', 'https://github.com/${GITHUB_USER}/${GITHUB_REPO}/commit/{commitid}',1,'${BRANCH}' WHERE NOT EXISTS(SELECT 1 FROM codespeed_project WHERE name = '${CODESPEED_NAME}')"

## run backfill script
./run_sandmark_backfill.py --run_stages ${RUN_STAGES} --branch ${BRANCH} --main_branch ${BRANCH} --repo ${REPO} --repo_pull --repo_reset_hard --use_repo_reference --max_hashes ${MAX_HASHES} --incremental_hashes --commit_choice_method from_hash=${FIRST_COMMIT} --executable_spec=${EXEC_SPEC} --environment ${ENVIRONMENT} --sandmark_comp_fmt https://github.com/${GITHUB_USER}/${GITHUB_REPO}/archive/{tag}.tar.gz --sandmark_tag_override ${OCAML_VERSION} --sandmark_iter 1 --sandmark_pre_exec="'taskset --cpu-list "${BENCH_CORE}" setarch `uname -m` --addr-no-randomize'" --sandmark_run_bench_targets ${BENCH_TARGETS} --archive_dir ${ARCHIVE_DIR} --codespeed_url ${CODESPEED_URL} --configure_options="${CONFIGURE_OPTIONS}" --ocamlrunparam="${OCAMLRUNPARAM}" --run_json ${RUN_JSON} --build_bench_target ${BUILD_BENCH_TARGET} --upload_project_name ${CODESPEED_NAME} -v ${RUNDIR}

'''

def shell_exec(cmd, verbose=args.verbose, check=False, stdout=None, stderr=None):
    if verbose:
        print('+ %s'%cmd)
    return subprocess.run(cmd, shell=True, check=check, stdout=stdout, stderr=stderr)

outdir = os.path.abspath(args.outdir)
if args.verbose: print('making directory: %s'%outdir)
shell_exec('mkdir -p %s'%outdir)

global_conf = {
	'scriptdir': SCRIPTDIR,
	'bench_targets': 'run_orun'
}

# read in yaml config
with open(args.config, 'r') as stream:
    try:
        conf = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print('YAMLError: %s'%exc)
        sys.exit(1)

# output the script
for run_conf in conf['tracked_branches']:
	fname = os.path.join(outdir, '%s.sh'%run_conf['codespeed_name'])
	with open(fname, 'w') as outfile:
		outfile.write(SCRIPT_PREAMBLE)
		conf_str = SCRIPT_PARAMS.format_map(SafeDict(**{**global_conf, **conf, **run_conf}))
		outfile.write(conf_str)
		outfile.write(SCRIPT_BODY)
	shell_exec('chmod +x %s'%fname)


