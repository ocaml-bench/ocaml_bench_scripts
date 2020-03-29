#!/usr/bin/env python3

"""
This script validates a given input YAML file for various checks
required to be performed prior to running the benchmarks in Sandmark.

Usage: $ python validate_yaml.py input.yml
"""

import argparse
import sys
import requests
import yaml

def check_branch_commit_exists(conf):
    """ Check if both input branch and commit exist in GitHub """
    for entry in conf['tracked_branches']:
        # Check branch exists
        branch = requests.get('https://github.com/%s/%s/tree/%s' %
                              (entry['github_user'], entry['github_repo'], entry['branch']))

        if branch.status_code != 200:
            print('Branch %s for %s/%s does not exist!' %
                  (entry['branch'], entry['github_user'], entry['github_repo']))

        # Check commit exists
        commit = requests.get('https://github.com/%s/%s/commit/%s' %
                              (entry['github_user'], entry['github_repo'], entry['first_commit']))

        if commit.status_code != 200:
            print('Commit %s for %s/%s does not exist!' %
                  (entry['first_commit'], entry['github_user'], entry['github_repo']))

def check_ocaml_version(conf):
    """ Check if OCaml version is in x.y.z format """
    for entry in conf['tracked_branches']:
        i = entry['ocaml_version'].split('.')

        if len(i) != 3:
            print('OCaml version needs (major, minor, patch) and not %s' %
                  (entry['ocaml_version']))

def check_unique_keys(conf, key):
    """ To identify if duplicate entries exist """
    keys = []
    for entry in conf['tracked_branches']:
        keys.append(entry[key])

    data = [i for i, x in enumerate(keys) if keys.count(x) > 1]
    if len(data) != 0:
        print('Duplicate %s entries exist in %s' % (key, data))

def validate(conf):
    """ The list of validation checks to be performed """
    check_branch_commit_exists(conf)
    check_ocaml_version(conf)
    check_unique_keys(conf, 'run_path_tag')
    check_unique_keys(conf, 'codespeed_name')

def main():
    """ The main function """
    parser = argparse.ArgumentParser(description=
                                     'Validate input YAML file before running bench scripts')
    parser.add_argument('config', type=str, help='config file')
    args = parser.parse_args()

    # read in yaml config
    with open(args.config, 'r') as stream:
        try:
            config = yaml.safe_load(stream)
            validate(config)
        except yaml.YAMLError as exc:
            print('YAMLError: %s'%exc)
            sys.exit(1)

if __name__ == "__main__":
    main()
