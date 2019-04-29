# Python module for getting git commits from the command line args

import datetime
import os
import subprocess
import sys


def parseISO8601Likedatetime(s):
	return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")

def get_git_hashes(args):
	def shell_exec(cmd, verbose=args.verbose, check=False, stdout=None, stderr=None):
		if verbose:
			print('+ %s'%cmd)
		return subprocess.run(cmd, shell=True, check=check, stdout=stdout, stderr=stderr)

	old_cwd = os.getcwd()
	repo_path = os.path.abspath(args.repo)
	if args.verbose: print('using repo: %s'%repo_path)
	os.chdir(repo_path)
	shell_exec('git checkout %s'%args.branch)
	if args.repo_pull:
		shell_exec('git pull')

	# git date notes:
	#   https://docs.microsoft.com/en-us/azure/devops/repos/git/git-dates?view=azure-devops
	commit_xtra_args = ' --date=local'
	if args.commit_after:
		commit_xtra_args += ' --after %s'%args.commit_after
	if args.commit_before:
		commit_xtra_args += ' --before %s'%args.commit_before

	commit_path = '%s..'%args.main_branch if args.main_branch != args.branch else ''

	# first parent notes:
	#   http://www.davidchudzicki.com/posts/first-parent/
	first_parent = '' if args.no_first_parent else '--first-parent'

	if args.commit_choice_method == 'version_tags':
		proc_output = shell_exec('git log %s --pretty=format:\'%%H %%s\' %s | grep VERSION | grep %s'%(first_parent, commit_xtra_args, args.branch), stdout=subprocess.PIPE)
		hash_comments = proc_output.stdout.decode('utf-8').split('\n')[::-1]
		hash_comments = filter(bool, hash_comments) # remove empty strings

		hashes = [hc.split(' ')[0] for hc in hash_comments]
		if args.verbose:
			for hc in hash_comments:
				print(hc)

	elif args.commit_choice_method == 'status_success':
		proc_output = shell_exec('git log %s %s --pretty=format:\'%%H\' %s' % (commit_path, first_parent, commit_xtra_args), stdout=subprocess.PIPE)
		all_hashes = proc_output.stdout.decode('utf-8').split('\n')[::-1]
		all_hashes = filter(bool, all_hashes) # remove empty strings

		def get_hash_status(h):
			curl_xtra_args = '-s'
			if args.github_oauth_token is not None:
				curl_xtra_args = curl_xtra_args + ' -H "Authorization: token %s"'%args.github_oauth_token
			proc_output = shell_exec('curl %s https://api.github.com/repos/ocaml/ocaml/commits/%s/status | jq .state'%(curl_xtra_args, h), stdout=subprocess.PIPE)
			return proc_output.stdout.decode('utf-8').strip().strip('"')

		hashes = []
		for h in all_hashes:
			state = get_hash_status(h)
			if args.verbose: print('%s is state of %s'%(state, h))
			if state == 'success':
				hashes.append(h)


	elif args.commit_choice_method.startswith('hash='):
		hashes = args.commit_choice_method.split('=')[1]
		hashes = hashes.split(',')

	elif args.commit_choice_method.startswith('delay=') or args.commit_choice_method == 'all':
		# Need to batch the commits that happen on the same timestamp:
		#  - often the build will not work properly if you don't do this
		#  - codespeed will re-order the commits based on hash that occur on same timestamp
		if args.commit_choice_method == 'all':
			h, m, s = 0, 0, 0
		else:
			time_str = args.commit_choice_method.split('=')[1]
			h, m, s = map(int, time_str.split(':'))
		dur = datetime.timedelta(hours=h, minutes=m, seconds=s)

		proc_output = shell_exec('git log %s %s --pretty=format:\'%%H/%%ci\' %s'%(commit_path, first_parent, commit_xtra_args), stdout=subprocess.PIPE)
		hash_commit_dates = proc_output.stdout.decode('utf-8').split('\n')[::-1]
		hash_commit_dates = filter(bool, hash_commit_dates) # remove empty strings

		hashes = []
		last_h = ''
		last_d = parseISO8601Likedatetime('1971-01-01 00:00:00 +0000')
		for hcd in hash_commit_dates:
			h, d = hcd.split('/')
			d = parseISO8601Likedatetime(d)
			if d - last_d > dur and last_h != '':
				if args.verbose: print('Taking %s %s'%(str(last_d), last_h))
				hashes.append(last_h)
			last_h, last_d = h, d
		if datetime.datetime.now(datetime.timezone.utc) - last_d >= dur:
			hashes.append(last_h)
			if args.verbose: print('Taking %s %s'%(str(last_d), last_h))

	else:
		print('Unknown commit choice method "%s"'%args.commit_choice_method)
		sys.exit(1)

	hashes = [ h for h in hashes if h ] # filter any null hashes
	hashes = hashes[-args.max_hashes:]

	os.chdir(old_cwd)
	return hashes
