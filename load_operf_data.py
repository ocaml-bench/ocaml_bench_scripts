#!/usr/bin/env python3

import argparse
import datetime
import glob
import json
import os
import yaml
import subprocess
import urllib.error
import urllib.parse
import urllib.request

GLOB_PATTERN = '*.summary'
CODESPEED_URL = 'http://localhost:8000/'

parser = argparse.ArgumentParser(description='Load operf-micro summary files into codespeed')
parser.add_argument('resultdir', type=str, help='directory of results')
parser.add_argument('--codespeed_url', type=str, help='url of codespeed server', default=CODESPEED_URL)
parser.add_argument('--glob_pattern', type=str, help='glob pattern for summary files', default=GLOB_PATTERN)
parser.add_argument('--halt_on_bad_parse', action='store_true', default=False)
parser.add_argument('--dry_run', action='store_true', default=False)
parser.add_argument('-v', '--verbose', action='store_true', default=False)

args = parser.parse_args()

def get_bench_dict(name, context, results):
    return {
        'commitid': context['commitid'],
        'project': context['project'],
        'branch': context['branch'],
        'executable': context['executable'],
        'environment': context['environment'],
        'benchmark': name,
        'units': 'cycles',
        'units_title': 'Time',
        'result_value': results['mean'],
        'min': results['min'],
        'max': results['max'],
        'std_dev': results['standard_error'],
    }

def parse_results(fname, context):
    bench_data = []
    with open(fname) as f:
        dat = yaml.safe_load(f)

        # first key in dat is always the bench run timestamp
        benchmarks = dat[list(dat.keys())[0]]

        # first key in bench is the name of the bench suite
        for k1 in benchmarks.keys():
            # second key in bench is either the subname or subgroup
            for k2 in benchmarks[k1].keys():
                # handle groups
                if k2.startswith('group '):
                    for k3 in benchmarks[k1][k2].keys():
                        k2_out = k2.replace('group ', '')
                        bench_data.append(get_bench_dict('%s/%s/%s'%(k1,k2_out,k3), context, benchmarks[k1][k2][k3]))
                else:
                    bench_data.append(get_bench_dict('%s/%s'%(k1,k2), context, benchmarks[k1][k2]))

    return bench_data


def get_context(dir, verbose=args.verbose):
    def ld(x):
        fname = os.path.join(dir, x)
        if verbose: print('loading context info from %s'%fname)
        with open(fname) as f:
            return yaml.safe_load(f)

    context = {}
    context.update(ld('build_context.conf'))
    context.update(ld('run_context.conf'))

    return context


def post_data_to_server(codespeed_url, data, dry_run=False, verbose=False):
    json_data = {'json': json.dumps(data)}
    url = '%sresult/add/json/' % codespeed_url
    data_payload = urllib.parse.urlencode(json_data).encode('ascii')

    if dry_run:
        print('DRY_RUN would have sent request: ')
        print(' url: %s'%url)
        print(' data: %s'%data_payload)
        return

    if verbose:
        print('requesting url=%s  data=%s'%(url, data_payload))

    response = "None"
    try:
        f = urllib.request.urlopen(url, data_payload)
    except urllib.error.HTTPError as e:
        print(str(e))
        print(e.read())
        return
    response = f.read()
    f.close()
    print("Server (%s) response: %s\n" % (CODESPEED_URL, response))


# load context information
context = get_context(args.resultdir)
if args.verbose:
    print('got context: \n%s'%yaml.dump(context, default_flow_style=False))

# get file list
glob_str = '%s/%s'%(args.resultdir, args.glob_pattern)
if args.verbose:
    print('taking result files of the form: %s'%glob_str)

for f in sorted(glob.glob(glob_str)):
    if args.verbose:
        print('processing %s'%f)

    try:
        results = parse_results(f, context)
    except:
        print('ERROR: failed to parse results in %s'%f)
        if args.halt_on_bad_parse:
            sys.exit(1)

    if args.verbose:
        print('loaded: \n%s'%yaml.dump(results, default_flow_style=False))

    post_data_to_server(args.codespeed_url, results, dry_run=args.dry_run, verbose=args.verbose)


