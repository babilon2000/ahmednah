
Unnamed repository; edit this file 'description' to name the repository.

[core]
	repositoryformatversion = 0
	filemode = true
	bare = false
	logallrefupdates = true
[user]
	name = ahmednah
	email = ahmednah@users.noreply.github.com

#!/bin/sh
#
# An example hook script to verify what is about to be committed
# by applypatch from an e-mail message.
#
# The hook should exit with non-zero status after issuing an
# appropriate message if it wants to stop the commit.
#
# To enable this hook, rename this file to "pre-applypatch".

. git-sh-setup
precommit="$(git rev-parse --git-path hooks/pre-commit)"
test -x "$precommit" && exec "$precommit" ${1+"$@"}
:

#!/bin/sh

# An example hook script to verify what is about to be pushed.  Called by "git
# push" after it has checked the remote status, but before anything has been
# pushed.  If this script exits with a non-zero status nothing will be pushed.
#
# This hook is called with the following parameters:
#
# $1 -- Name of the remote to which the push is being done
# $2 -- URL to which the push is being done
#
# If pushing without using a named remote those arguments will be equal.
#
# Information about the commits which are being pushed is supplied as lines to
# the standard input in the form:
#
#   <local ref> <local oid> <remote ref> <remote oid>
#
# This sample shows how to prevent push of commits where the log message starts
# with "WIP" (work in progress).

remote="$1"
url="$2"

zero=$(git hash-object --stdin </dev/null | tr '[0-9a-f]' '0')

while read local_ref local_oid remote_ref remote_oid
do
	if test "$local_oid" = "$zero"
	then
		# Handle delete
		:
	else
		if test "$remote_oid" = "$zero"
		then
			# New branch, examine all commits
			range="$local_oid"
		else
			# Update to existing branch, examine new commits
			range="$remote_oid..$local_oid"
		fi

		# Check for WIP commit
		commit=$(git rev-list -n 1 --grep '^WIP' "$range")
		if test -n "$commit"
		then
			echo >&2 "Found WIP commit in $local_ref, not pushing"
			exit 1
		fi
	fi
done

exit 0

#!/bin/sh

# An example hook script to validate a patch (and/or patch series) before
# sending it via email.
#
# The hook should exit with non-zero status after issuing an appropriate
# message if it wants to prevent the email(s) from being sent.
#
# To enable this hook, rename this file to "sendemail-validate".
#
# By default, it will only check that the patch(es) can be applied on top of
# the default upstream branch without conflicts in a secondary worktree. After
# validation (successful or not) of the last patch of a series, the worktree
# will be deleted.
#
# The following config variables can be set to change the default remote and
# remote ref that are used to apply the patches against:
#
#   sendemail.validateRemote (default: origin)
#   sendemail.validateRemoteRef (default: HEAD)
#
# Replace the TODO placeholders with appropriate checks according to your
# needs.

validate_cover_letter () {
	file="$1"
	# TODO: Replace with appropriate checks (e.g. spell checking).
	true
}

validate_patch () {
	file="$1"
	# Ensure that the patch applies without conflicts.
	git am -3 "$file" || return
	# TODO: Replace with appropriate checks for this patch
	# (e.g. checkpatch.pl).
	true
}

validate_series () {
	# TODO: Replace with appropriate checks for the whole series
	# (e.g. quick build, coding style checks, etc.).
	true
}

# main -------------------------------------------------------------------------

if test "$GIT_SENDEMAIL_FILE_COUNTER" = 1
then
	remote=$(git config --default origin --get sendemail.validateRemote) &&
	ref=$(git config --default HEAD --get sendemail.validateRemoteRef) &&
	worktree=$(mktemp --tmpdir -d sendemail-validate.XXXXXXX) &&
	git worktree add -fd --checkout "$worktree" "refs/remotes/$remote/$ref" &&
	git config --replace-all sendemail.validateWorktree "$worktree"
else
	worktree=$(git config --get sendemail.validateWorktree)
fi || {
	echo "sendemail-validate: error: failed to prepare worktree" >&2
	exit 1
}

unset GIT_DIR GIT_WORK_TREE
cd "$worktree" &&

if grep -q "^diff --git " "$1"
then
	validate_patch "$1"
else
	validate_cover_letter "$1"
fi &&

if test "$GIT_SENDEMAIL_FILE_COUNTER" = "$GIT_SENDEMAIL_FILE_TOTAL"
then
	git config --unset-all sendemail.validateWorktree &&
	trap 'git worktree remove -ff "$worktree"' EXIT &&
	validate_series
fi

#!/usr/bin/perl

use strict;
use warnings;
use IPC::Open2;

# An example hook script to integrate Watchman
# (https://facebook.github.io/watchman/) with git to speed up detecting
# new and modified files.
#
# The hook is passed a version (currently 2) and last update token
# formatted as a string and outputs to stdout a new update token and
# all files that have been modified since the update token. Paths must
# be relative to the root of the working tree and separated by a single NUL.
#
# To enable this hook, rename this file to "query-watchman" and set
# 'git config core.fsmonitor .git/hooks/query-watchman'
#
my ($version, $last_update_token) = @ARGV;

# Uncomment for debugging
# print STDERR "$0 $version $last_update_token\n";

# Check the hook interface version
if ($version ne 2) {
	die "Unsupported query-fsmonitor hook version '$version'.\n" .
	    "Falling back to scanning...\n";
}

my $git_work_tree = get_working_dir();

my $retry = 1;

my $json_pkg;
eval {
	require JSON::XS;
	$json_pkg = "JSON::XS";
	1;
} or do {
	require JSON::PP;
	$json_pkg = "JSON::PP";
};

launch_watchman();

sub launch_watchman {
	my $o = watchman_query();
	if (is_work_tree_watched($o)) {
		output_result($o->{clock}, @{$o->{files}});
	}
}

sub output_result {
	my ($clockid, @files) = @_;

	# Uncomment for debugging watchman output
	# open (my $fh, ">", ".git/watchman-output.out");
	# binmode $fh, ":utf8";
	# print $fh "$clockid\n@files\n";
	# close $fh;

	binmode STDOUT, ":utf8";
	print $clockid;
	print "\0";
	local $, = "\0";
	print @files;
}

sub watchman_clock {
	my $response = qx/watchman clock "$git_work_tree"/;
	die "Failed to get clock id on '$git_work_tree'.\n" .
		"Falling back to scanning...\n" if $? != 0;

	return $json_pkg->new->utf8->decode($response);
}

sub watchman_query {
	my $pid = open2(\*CHLD_OUT, \*CHLD_IN, 'watchman -j --no-pretty')
	or die "open2() failed: $!\n" .
	"Falling back to scanning...\n";

	# In the query expression below we're asking for names of files that
	# changed since $last_update_token but not from the .git folder.
	#
	# To accomplish this, we're using the "since" generator to use the
	# recency index to select candidate nodes and "fields" to limit the
	# output to file names only. Then we're using the "expression" term to
	# further constrain the results.
	my $last_update_line = "";
	if (substr($last_update_token, 0, 1) eq "c") {
		$last_update_token = "\"$last_update_token\"";
		$last_update_line = qq[\n"since": $last_update_token,];
	}
	my $query = <<"	END";
		["query", "$git_work_tree", {$last_update_line
			"fields": ["name"],
			"expression": ["not", ["dirname", ".git"]]
		}]
	END

	# Uncomment for debugging the watchman query
	# open (my $fh, ">", ".git/watchman-query.json");
	# print $fh $query;
	# close $fh;

	print CHLD_IN $query;
	close CHLD_IN;
	my $response = do {local $/; <CHLD_OUT>};

	# Uncomment for debugging the watch response
	# open ($fh, ">", ".git/watchman-response.json");
	# print $fh $response;
	# close $fh;

	die "Watchman: command returned no output.\n" .
	"Falling back to scanning...\n" if $response eq "";
	die "Watchman: command returned invalid output: $response\n" .
	"Falling back to scanning...\n" unless $response =~ /^\{/;

	return $json_pkg->new->utf8->decode($response);
}

sub is_work_tree_watched {
	my ($output) = @_;
	my $error = $output->{error};
	if ($retry > 0 and $error and $error =~ m/unable to resolve root .* directory (.*) is not watched/) {
		$retry--;
		my $response = qx/watchman watch "$git_work_tree"/;
		die "Failed to make watchman watch '$git_work_tree'.\n" .
		    "Falling back to scanning...\n" if $? != 0;
		$output = $json_pkg->new->utf8->decode($response);
		$error = $output->{error};
		die "Watchman: $error.\n" .
		"Falling back to scanning...\n" if $error;

		# Uncomment for debugging watchman output
		# open (my $fh, ">", ".git/watchman-output.out");
		# close $fh;

		# Watchman will always return all files on the first query so
		# return the fast "everything is dirty" flag to git and do the
		# Watchman query just to get it over with now so we won't pay
		# the cost in git to look up each individual file.
		my $o = watchman_clock();
		$error = $output->{error};

		die "Watchman: $error.\n" .
		"Falling back to scanning...\n" if $error;

		output_result($o->{clock}, ("/"));
		$last_update_token = $o->{clock};

		eval { launch_watchman() };
		return 0;
	}

	die "Watchman: $error.\n" .
	"Falling back to scanning...\n" if $error;

	return 1;
}

sub get_working_dir {
	my $working_dir;
	if ($^O =~ 'msys' || $^O =~ 'cygwin') {
		$working_dir = Win32::GetCwd();
		$working_dir =~ tr/\\/\//;
	} else {
		require Cwd;
		$working_dir = Cwd::cwd();
	}

	return $working_dir;
}

#!/bin/sh
#
# An example hook script to check the commit log message.
# Called by "git commit" with one argument, the name of the file
# that has the commit message.  The hook should exit with non-zero
# status after issuing an appropriate message if it wants to stop the
# commit.  The hook is allowed to edit the commit message file.
#
# To enable this hook, rename this file to "commit-msg".

# Uncomment the below to add a Signed-off-by line to the message.
# Doing this in a hook is a bad idea in general, but the prepare-commit-msg
# hook is more suited to it.
#
# SOB=$(git var GIT_AUTHOR_IDENT | sed -n 's/^\(.*>\).*$/Signed-off-by: \1/p')
# grep -qs "^$SOB" "$1" || echo "$SOB" >> "$1"

# This example catches duplicate Signed-off-by lines.

test "" = "$(grep '^Signed-off-by: ' "$1" |
	 sort | uniq -c | sed -e '/^[ 	]*1[ 	]/d')" || {
	echo >&2 Duplicate Signed-off-by lines.
	exit 1
}

#!/bin/sh
#
# An example hook script to prepare a packed repository for use over
# dumb transports.
#
# To enable this hook, rename this file to "post-update".

exec git update-server-info

#!/bin/sh
#
# An example hook script to block unannotated tags from entering.
# Called by "git receive-pack" with arguments: refname sha1-old sha1-new
#
# To enable this hook, rename this file to "update".
#
# Config
# ------
# hooks.allowunannotated
#   This boolean sets whether unannotated tags will be allowed into the
#   repository.  By default they won't be.
# hooks.allowdeletetag
#   This boolean sets whether deleting tags will be allowed in the
#   repository.  By default they won't be.
# hooks.allowmodifytag
#   This boolean sets whether a tag may be modified after creation. By default
#   it won't be.
# hooks.allowdeletebranch
#   This boolean sets whether deleting branches will be allowed in the
#   repository.  By default they won't be.
# hooks.denycreatebranch
#   This boolean sets whether remotely creating branches will be denied
#   in the repository.  By default this is allowed.
#

# --- Command line
refname="$1"
oldrev="$2"
newrev="$3"

# --- Safety check
if [ -z "$GIT_DIR" ]; then
	echo "Don't run this script from the command line." >&2
	echo " (if you want, you could supply GIT_DIR then run" >&2
	echo "  $0 <ref> <oldrev> <newrev>)" >&2
	exit 1
fi

if [ -z "$refname" -o -z "$oldrev" -o -z "$newrev" ]; then
	echo "usage: $0 <ref> <oldrev> <newrev>" >&2
	exit 1
fi

# --- Config
allowunannotated=$(git config --type=bool hooks.allowunannotated)
allowdeletebranch=$(git config --type=bool hooks.allowdeletebranch)
denycreatebranch=$(git config --type=bool hooks.denycreatebranch)
allowdeletetag=$(git config --type=bool hooks.allowdeletetag)
allowmodifytag=$(git config --type=bool hooks.allowmodifytag)

# check for no description
projectdesc=$(sed -e '1q' "$GIT_DIR/description")
case "$projectdesc" in
"Unnamed repository"* | "")
	echo "*** Project description file hasn't been set" >&2
	exit 1
	;;
esac

# --- Check types
# if $newrev is 0000...0000, it's a commit to delete a ref.
zero=$(git hash-object --stdin </dev/null | tr '[0-9a-f]' '0')
if [ "$newrev" = "$zero" ]; then
	newrev_type=delete
else
	newrev_type=$(git cat-file -t $newrev)
fi

case "$refname","$newrev_type" in
	refs/tags/*,commit)
		# un-annotated tag
		short_refname=${refname##refs/tags/}
		if [ "$allowunannotated" != "true" ]; then
			echo "*** The un-annotated tag, $short_refname, is not allowed in this repository" >&2
			echo "*** Use 'git tag [ -a | -s ]' for tags you want to propagate." >&2
			exit 1
		fi
		;;
	refs/tags/*,delete)
		# delete tag
		if [ "$allowdeletetag" != "true" ]; then
			echo "*** Deleting a tag is not allowed in this repository" >&2
			exit 1
		fi
		;;
	refs/tags/*,tag)
		# annotated tag
		if [ "$allowmodifytag" != "true" ] && git rev-parse $refname > /dev/null 2>&1
		then
			echo "*** Tag '$refname' already exists." >&2
			echo "*** Modifying a tag is not allowed in this repository." >&2
			exit 1
		fi
		;;
	refs/heads/*,commit)
		# branch
		if [ "$oldrev" = "$zero" -a "$denycreatebranch" = "true" ]; then
			echo "*** Creating a branch is not allowed in this repository" >&2
			exit 1
		fi
		;;
	refs/heads/*,delete)
		# delete branch
		if [ "$allowdeletebranch" != "true" ]; then
			echo "*** Deleting a branch is not allowed in this repository" >&2
			exit 1
		fi
		;;
	refs/remotes/*,commit)
		# tracking branch
		;;
	refs/remotes/*,delete)
		# delete tracking branch
		if [ "$allowdeletebranch" != "true" ]; then
			echo "*** Deleting a tracking branch is not allowed in this repository" >&2
			exit 1
		fi
		;;
	*)
		# Anything else (is there anything else?)
		echo "*** Update hook: unknown type of update to ref $refname of type $newrev_type" >&2
		exit 1
		;;
esac

# --- Finished
exit 0

#!/bin/sh
#
# An example hook script to verify what is about to be committed.
# Called by "git commit" with no arguments.  The hook should
# exit with non-zero status after issuing an appropriate message if
# it wants to stop the commit.
#
# To enable this hook, rename this file to "pre-commit".

if git rev-parse --verify HEAD >/dev/null 2>&1
then
	against=HEAD
else
	# Initial commit: diff against an empty tree object
	against=$(git hash-object -t tree /dev/null)
fi

# If you want to allow non-ASCII filenames set this variable to true.
allownonascii=$(git config --type=bool hooks.allownonascii)

# Redirect output to stderr.
exec 1>&2

# Cross platform projects tend to avoid non-ASCII filenames; prevent
# them from being added to the repository. We exploit the fact that the
# printable range starts at the space character and ends with tilde.
if [ "$allownonascii" != "true" ] &&
	# Note that the use of brackets around a tr range is ok here, (it's
	# even required, for portability to Solaris 10's /usr/bin/tr), since
	# the square bracket bytes happen to fall in the designated range.
	test $(git diff --cached --name-only --diff-filter=A -z $against |
	  LC_ALL=C tr -d '[ -~]\0' | wc -c) != 0
then
	cat <<\EOF
Error: Attempt to add a non-ASCII file name.

This can cause problems if you want to work with people on other platforms.

To be portable it is advisable to rename the file.

If you know what you are doing you can disable this check using:

  git config hooks.allownonascii true
EOF
	exit 1
fi

# If there are whitespace errors, print the offending file names and fail.
exec git diff-index --check --cached $against --

#!/bin/sh
#
# Copyright (c) 2006, 2008 Junio C Hamano
#
# The "pre-rebase" hook is run just before "git rebase" starts doing
# its job, and can prevent the command from running by exiting with
# non-zero status.
#
# The hook is called with the following parameters:
#
# $1 -- the upstream the series was forked from.
# $2 -- the branch being rebased (or empty when rebasing the current branch).
#
# This sample shows how to prevent topic branches that are already
# merged to 'next' branch from getting rebased, because allowing it
# would result in rebasing already published history.

publish=next
basebranch="$1"
if test "$#" = 2
then
	topic="refs/heads/$2"
else
	topic=`git symbolic-ref HEAD` ||
	exit 0 ;# we do not interrupt rebasing detached HEAD
fi

case "$topic" in
refs/heads/??/*)
	;;
*)
	exit 0 ;# we do not interrupt others.
	;;
esac

# Now we are dealing with a topic branch being rebased
# on top of master.  Is it OK to rebase it?

# Does the topic really exist?
git show-ref -q "$topic" || {
	echo >&2 "No such branch $topic"
	exit 1
}

# Is topic fully merged to master?
not_in_master=`git rev-list --pretty=oneline ^master "$topic"`
if test -z "$not_in_master"
then
	echo >&2 "$topic is fully merged to master; better remove it."
	exit 1 ;# we could allow it, but there is no point.
fi

# Is topic ever merged to next?  If so you should not be rebasing it.
only_next_1=`git rev-list ^master "^$topic" ${publish} | sort`
only_next_2=`git rev-list ^master           ${publish} | sort`
if test "$only_next_1" = "$only_next_2"
then
	not_in_topic=`git rev-list "^$topic" master`
	if test -z "$not_in_topic"
	then
		echo >&2 "$topic is already up to date with master"
		exit 1 ;# we could allow it, but there is no point.
	else
		exit 0
	fi
else
	not_in_next=`git rev-list --pretty=oneline ^${publish} "$topic"`
	/usr/bin/perl -e '
		my $topic = $ARGV[0];
		my $msg = "* $topic has commits already merged to public branch:\n";
		my (%not_in_next) = map {
			/^([0-9a-f]+) /;
			($1 => 1);
		} split(/\n/, $ARGV[1]);
		for my $elem (map {
				/^([0-9a-f]+) (.*)$/;
				[$1 => $2];
			} split(/\n/, $ARGV[2])) {
			if (!exists $not_in_next{$elem->[0]}) {
				if ($msg) {
					print STDERR $msg;
					undef $msg;
				}
				print STDERR " $elem->[1]\n";
			}
		}
	' "$topic" "$not_in_next" "$not_in_master"
	exit 1
fi

<<\DOC_END

This sample hook safeguards topic branches that have been
published from being rewound.

The workflow assumed here is:

 * Once a topic branch forks from "master", "master" is never
   merged into it again (either directly or indirectly).

 * Once a topic branch is fully cooked and merged into "master",
   it is deleted.  If you need to build on top of it to correct
   earlier mistakes, a new topic branch is created by forking at
   the tip of the "master".  This is not strictly necessary, but
   it makes it easier to keep your history simple.

 * Whenever you need to test or publish your changes to topic
   branches, merge them into "next" branch.

The script, being an example, hardcodes the publish branch name
to be "next", but it is trivial to make it configurable via
$GIT_DIR/config mechanism.

With this workflow, you would want to know:

(1) ... if a topic branch has ever been merged to "next".  Young
    topic branches can have stupid mistakes you would rather
    clean up before publishing, and things that have not been
    merged into other branches can be easily rebased without
    affecting other people.  But once it is published, you would
    not want to rewind it.

(2) ... if a topic branch has been fully merged to "master".
    Then you can delete it.  More importantly, you should not
    build on top of it -- other people may already want to
    change things related to the topic as patches against your
    "master", so if you need further changes, it is better to
    fork the topic (perhaps with the same name) afresh from the
    tip of "master".

Let's look at this example:

		   o---o---o---o---o---o---o---o---o---o "next"
		  /       /           /           /
		 /   a---a---b A     /           /
		/   /               /           /
	       /   /   c---c---c---c B         /
	      /   /   /             \         /
	     /   /   /   b---b C     \       /
	    /   /   /   /             \     /
    ---o---o---o---o---o---o---o---o---o---o---o "master"


A, B and C are topic branches.

 * A has one fix since it was merged up to "next".

 * B has finished.  It has been fully merged up to "master" and "next",
   and is ready to be deleted.

 * C has not merged to "next" at all.

We would want to allow C to be rebased, refuse A, and encourage
B to be deleted.

To compute (1):

	git rev-list ^master ^topic next
	git rev-list ^master        next

	if these match, topic has not merged in next at all.

To compute (2):

	git rev-list master..topic

	if this is empty, it is fully merged to "master".

DOC_END

#!/bin/sh
#
# An example hook script to prepare the commit log message.
# Called by "git commit" with the name of the file that has the
# commit message, followed by the description of the commit
# message's source.  The hook's purpose is to edit the commit
# message file.  If the hook fails with a non-zero status,
# the commit is aborted.
#
# To enable this hook, rename this file to "prepare-commit-msg".

# This hook includes three examples. The first one removes the
# "# Please enter the commit message..." help message.
#
# The second includes the output of "git diff --name-status -r"
# into the message, just before the "git status" output.  It is
# commented because it doesn't cope with --amend or with squashed
# commits.
#
# The third example adds a Signed-off-by line to the message, that can
# still be edited.  This is rarely a good idea.

COMMIT_MSG_FILE=$1
COMMIT_SOURCE=$2
SHA1=$3

/usr/bin/perl -i.bak -ne 'print unless(m/^. Please enter the commit message/..m/^#$/)' "$COMMIT_MSG_FILE"

# case "$COMMIT_SOURCE,$SHA1" in
#  ,|template,)
#    /usr/bin/perl -i.bak -pe '
#       print "\n" . `git diff --cached --name-status -r`
# 	 if /^#/ && $first++ == 0' "$COMMIT_MSG_FILE" ;;
#  *) ;;
# esac

# SOB=$(git var GIT_COMMITTER_IDENT | sed -n 's/^\(.*>\).*$/Signed-off-by: \1/p')
# git interpret-trailers --in-place --trailer "$SOB" "$COMMIT_MSG_FILE"
# if test -z "$COMMIT_SOURCE"
# then
#   /usr/bin/perl -i.bak -pe 'print "\n" if !$first_line++' "$COMMIT_MSG_FILE"
# fi

#!/bin/sh

# An example hook script to update a checked-out tree on a git push.
#
# This hook is invoked by git-receive-pack(1) when it reacts to git
# push and updates reference(s) in its repository, and when the push
# tries to update the branch that is currently checked out and the
# receive.denyCurrentBranch configuration variable is set to
# updateInstead.
#
# By default, such a push is refused if the working tree and the index
# of the remote repository has any difference from the currently
# checked out commit; when both the working tree and the index match
# the current commit, they are updated to match the newly pushed tip
# of the branch. This hook is to be used to override the default
# behaviour; however the code below reimplements the default behaviour
# as a starting point for convenient modification.
#
# The hook receives the commit with which the tip of the current
# branch is going to be updated:
commit=$1

# It can exit with a non-zero status to refuse the push (when it does
# so, it must not modify the index or the working tree).
die () {
	echo >&2 "$*"
	exit 1
}

# Or it can make any necessary changes to the working tree and to the
# index to bring them to the desired state when the tip of the current
# branch is updated to the new commit, and exit with a zero status.
#
# For example, the hook can simply run git read-tree -u -m HEAD "$1"
# in order to emulate git fetch that is run in the reverse direction
# with git push, as the two-tree form of git read-tree -u -m is
# essentially the same as git switch or git checkout that switches
# branches while keeping the local changes in the working tree that do
# not interfere with the difference between the branches.

# The below is a more-or-less exact translation to shell of the C code
# for the default behaviour for git's push-to-checkout hook defined in
# the push_to_deploy() function in builtin/receive-pack.c.
#
# Note that the hook will be executed from the repository directory,
# not from the working tree, so if you want to perform operations on
# the working tree, you will have to adapt your code accordingly, e.g.
# by adding "cd .." or using relative paths.

if ! git update-index -q --ignore-submodules --refresh
then
	die "Up-to-date check failed"
fi

if ! git diff-files --quiet --ignore-submodules --
then
	die "Working directory has unstaged changes"
fi

# This is a rough translation of:
#
#   head_has_history() ? "HEAD" : EMPTY_TREE_SHA1_HEX
if git cat-file -e HEAD 2>/dev/null
then
	head=HEAD
else
	head=$(git hash-object -t tree --stdin </dev/null)
fi

if ! git diff-index --quiet --cached --ignore-submodules $head --
then
	die "Working directory has staged changes"
fi

if ! git read-tree -u -m "$commit"
then
	die "Could not update working tree to new HEAD"
fi

#!/bin/sh
#
# An example hook script to verify what is about to be committed.
# Called by "git merge" with no arguments.  The hook should
# exit with non-zero status after issuing an appropriate message to
# stderr if it wants to stop the merge commit.
#
# To enable this hook, rename this file to "pre-merge-commit".

. git-sh-setup
test -x "$GIT_DIR/hooks/pre-commit" &&
        exec "$GIT_DIR/hooks/pre-commit"
:

#!/bin/sh
#
# An example hook script to make use of push options.
# The example simply echoes all push options that start with 'echoback='
# and rejects all pushes when the "reject" push option is used.
#
# To enable this hook, rename this file to "pre-receive".

if test -n "$GIT_PUSH_OPTION_COUNT"
then
	i=0
	while test "$i" -lt "$GIT_PUSH_OPTION_COUNT"
	do
		eval "value=\$GIT_PUSH_OPTION_$i"
		case "$value" in
		echoback=*)
			echo "echo from the pre-receive-hook: ${value#*=}" >&2
			;;
		reject)
			exit 1
		esac
		i=$((i + 1))
	done
fi

#!/bin/sh
#
# An example hook script to check the commit log message taken by
# applypatch from an e-mail message.
#
# The hook should exit with non-zero status after issuing an
# appropriate message if it wants to stop the commit.  The hook is
# allowed to edit the commit message file.
#
# To enable this hook, rename this file to "applypatch-msg".

. git-sh-setup
commitmsg="$(git rev-parse --git-path hooks/commit-msg)"
test -x "$commitmsg" && exec "$commitmsg" ${1+"$@"}
:

x+)JMU04�d040031QH��MM�K̈�/H���K/�+�dP�~)^�k���ѯ�����ДLt��99�z)�yn_�;���n�:�p�ҶWS̸���J�ۡ�y��Έ��Zr��ۏS;�3TqRifNJ|JeH��[jY��̗�:În書A�{2 b'G�
x+)JMU0�d040031QH��K�L�+���aP�i~�1SлeW���2���8�� `�:
xK��OR0�d(��--HI��5�32�*.)JM���,�M
�
�R��l����R�
*+r�l���
2sr���l

�� ���
ahmednah: PDF floor plan to Revit (phases 1-4)

- PDF line extraction with PyMuPDF, wall detection from parallel lines
- Corner joining, origin normalization, door/window detection
- Dynamo graph: walls via Wall.ByCurveAndHeight + doors/windows as FamilyInstance
- Streamlit web app ready for Streamlit Community Cloud

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015tnNXhWmXiHBZ2uGKaRNeX

01f7652bf423145ce586169b2dbb23edb7f42624

0000000000000000000000000000000000000000 01f7652bf423145ce586169b2dbb23edb7f42624 ahmednah <ahmednah@users.noreply.github.com> 1794973184 +0400	commit (initial): ahmednah: PDF floor plan to Revit (phases 1-4)

0000000000000000000000000000000000000000 01f7652bf423145ce586169b2dbb23edb7f42624 ahmednah <ahmednah@users.noreply.github.com> 1794973184 +0400	commit (initial): ahmednah: PDF floor plan to Revit (phases 1-4)

ref: refs/heads/master

# git ls-files --others --exclude-from=.git/info/exclude
# Lines that start with '#' are comments.
# For a project mostly in C, the following would be a good set of
# exclude patterns (uncomment them if you want to use them):
# *.[oa]
# *~

[server]
# أقصى حجم لملف PDF المرفوع (ميغابايت)
maxUploadSize = 50

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#C8553D"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F4F1EC"
textColor = "#1F2A37"

"""
pdf_extractor.py
----------------
قراءة ملف PDF (مخطط أرضي مصدَّر من AutoCAD) واستخراج كل الخطوط منه.

الفكرة:
- AutoCAD عند التصدير إلى PDF يحوّل الخطوط والـ Polylines إلى "مسارات متجهية" (vector paths).
- PyMuPDF يعطينا هذه المسارات عبر page.get_drawings().
- كل مسار يحتوي عناصر: "l" خط مستقيم، "re" مستطيل، "qu" رباعي، "c" منحنى بيزيه.
- نأخذ الخطوط المستقيمة، ونفكك المستطيلات والرباعيات إلى 4 خطوط.
- المنحنيات (أقواس الأبواب مثلاً) نتجاهلها في هذه المرحلة.

نظام الإحداثيات:
- PDF في PyMuPDF: الأصل أعلى يسار الصفحة، ومحور Y للأسفل، والوحدة "point" (1/72 إنش).
- نحن نحوّل إلى: الأصل أسفل يسار، ومحور Y للأعلى (مثل AutoCAD و Revit)، والوحدة متر حقيقي.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import pymupdf  # PyMuPDF

POINT_TO_MM = 25.4 / 72.0  # 1 point = 0.3528 mm على الورق


@dataclass
class Line:
    id: int
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    stroke_width: float  # سماكة الخط المرسوم (بالمتر الحقيقي بعد تطبيق المقياس)
    color: tuple | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def paper_to_real_factor(scale: float) -> float:
    """
    معامل التحويل من point (على الورق) إلى متر (في الواقع).
    مثال: مقياس 1:100 → 1 point = 0.3528 mm ورق = 35.28 mm واقع = 0.03528 m
    """
    return POINT_TO_MM * scale / 1000.0


def _segments_from_drawing(d: dict):
    """يحوّل عناصر مسار واحد إلى قائمة مقاطع ((x1,y1),(x2,y2))."""
    segs = []
    for item in d["items"]:
        kind = item[0]
        if kind == "l":  # خط مستقيم
            p1, p2 = item[1], item[2]
            segs.append(((p1.x, p1.y), (p2.x, p2.y)))
        elif kind == "re":  # مستطيل → 4 أضلاع
            r = item[1]
            c = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
            segs += [(c[i], c[(i + 1) % 4]) for i in range(4)]
        elif kind == "qu":  # رباعي (مستطيل مدوّر مثلاً) → 4 أضلاع
            q = item[1]
            c = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
            segs += [(c[i], c[(i + 1) % 4]) for i in range(4)]
        # "c" منحنيات: تُجمع منفصلة في extract_lines (أقواس الأبواب)
    return segs


def extract_lines(
    pdf_path_or_bytes,
    page_number: int = 0,
    scale: float = 100.0,
    min_length_m: float = 0.05,
) -> tuple[list[Line], dict]:
    """
    يستخرج كل الخطوط من صفحة واحدة.

    المعاملات:
        pdf_path_or_bytes : مسار الملف أو محتواه bytes (من Streamlit)
        page_number       : رقم الصفحة (يبدأ من 0)
        scale             : مقياس الرسم، 100 يعني 1:100
        min_length_m      : تجاهل الخطوط الأقصر من هذا الطول (بالمتر) — ضجيج/نصوص/تهشير

    يرجع:
        (قائمة الخطوط, معلومات الصفحة)
    """
    if isinstance(pdf_path_or_bytes, (bytes, bytearray)):
        doc = pymupdf.open(stream=pdf_path_or_bytes, filetype="pdf")
    else:
        doc = pymupdf.open(pdf_path_or_bytes)

    page = doc[page_number]
    page_h = page.rect.height
    k = paper_to_real_factor(scale)

    lines: list[Line] = []
    arcs: list[list[tuple[float, float]]] = []  # منحنيات بيزيه (أقواس الأبواب) — 4 نقاط لكل منحنى
    seen: set = set()

    for d in page.get_drawings():
        width_pt = d.get("width") or 0.0
        color = d.get("color")
        for item in d["items"]:
            if item[0] == "c":
                arcs.append([(round(p.x * k, 4), round((page_h - p.y) * k, 4)) for p in item[1:5]])
        for (ax, ay), (bx, by) in _segments_from_drawing(d):
            # قلب محور Y وتحويل الوحدة إلى متر
            x1, y1 = ax * k, (page_h - ay) * k
            x2, y2 = bx * k, (page_h - by) * k
            length = math.hypot(x2 - x1, y2 - y1)
            if length < min_length_m:
                continue

            # إزالة التكرار (AutoCAD أحياناً يرسم الخط مرتين)
            key = tuple(sorted([(round(x1, 3), round(y1, 3)), (round(x2, 3), round(y2, 3))]))
            if key in seen:
                continue
            seen.add(key)

            lines.append(
                Line(
                    id=len(lines) + 1,
                    x1=round(x1, 4), y1=round(y1, 4),
                    x2=round(x2, 4), y2=round(y2, 4),
                    length=round(length, 4),
                    stroke_width=round(width_pt * k, 5),
                    color=tuple(round(c, 3) for c in color) if color else None,
                )
            )

    info = {
        "pages": len(doc),
        "page_width_m": round(page.rect.width * k, 3),
        "page_height_m": round(page_h * k, 3),
        "factor_m_per_pt": k,
        "arcs": arcs,
    }
    doc.close()
    return lines, info


def render_page_png(pdf_bytes: bytes, page_number: int = 0, zoom: float = 2.0) -> bytes:
    """يحوّل صفحة PDF إلى صورة PNG لعرضها في الواجهة."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[page_number].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    png = pix.tobytes("png")
    doc.close()
    return png


"""
wall_joiner.py
--------------
تنظيف الجدران قبل إرسالها إلى Revit:

1) وصل الزوايا (L) والتقاطعات (T):
   خط المحور الناتج من wall_detector يقف عند الوجه الداخلي للجدار المجاور،
   فيبقى فراغ عند كل زاوية. هنا نمدّ (أو نقص) طرف كل جدار حتى يلتقي
   بمحور الجدار العمودي عليه. Revit بعدها يصنع الـ Join تلقائياً.

2) نقل الأصل: نجعل أسفل يسار المبنى هو النقطة (0,0) بدل زاوية الورقة.
"""

from __future__ import annotations

import math

from .wall_detector import Wall


def _intersect(p1, p2, p3, p4):
    """تقاطع المستقيمين اللانهائيين (p1p2) و (p3p4). يرجع None إذا كانا متوازيين."""
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (p4[0] - p3[0], p4[1] - p3[1])
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    n1, n2 = math.hypot(*d1), math.hypot(*d2)
    if n1 == 0 or n2 == 0 or abs(cross) / (n1 * n2) < math.sin(math.radians(10)):
        return None
    t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / cross
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


def _param_on(seg_a, seg_b, p):
    """موقع النقطة p على امتداد القطعة (a→b) بالمتر: 0 عند a و L عند b."""
    dx, dy = seg_b[0] - seg_a[0], seg_b[1] - seg_a[1]
    L = math.hypot(dx, dy)
    return ((p[0] - seg_a[0]) * dx + (p[1] - seg_a[1]) * dy) / L, L


def join_walls(walls: list[Wall]) -> list[Wall]:
    pts = [[(w.x1, w.y1), (w.x2, w.y2)] for w in walls]
    orig = [list(p) for p in pts]  # المستقيمات اللانهائية لا تتغير بتحريك الأطراف

    for i, wi in enumerate(walls):
        for end in (0, 1):
            e = orig[i][end]
            best, best_d = None, None
            for j, wj in enumerate(walls):
                if i == j:
                    continue
                P = _intersect(orig[i][0], orig[i][1], orig[j][0], orig[j][1])
                if P is None:
                    continue
                tol = max(wi.thickness, wj.thickness) * 0.75 + 0.02
                d = math.hypot(P[0] - e[0], P[1] - e[1])
                if d > tol:
                    continue
                s, Lj = _param_on(orig[j][0], orig[j][1], P)
                if s < -tol or s > Lj + tol:
                    continue
                if best_d is None or d < best_d:
                    best, best_d = P, d
            if best is not None:
                pts[i][end] = best

    out = []
    for w, ((x1, y1), (x2, y2)) in zip(walls, pts):
        out.append(Wall(w.wall_id, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3),
                        round(math.hypot(x2 - x1, y2 - y1), 3), w.thickness, w.line_a, w.line_b))
    return out


def normalize_origin(walls: list[Wall]) -> tuple[list[Wall], tuple[float, float]]:
    """يزيح كل الجدران بحيث يصبح أسفل يسار المبنى (0,0). يرجع الإزاحة لاستخدامها لاحقاً (الأبواب)."""
    if not walls:
        return walls, (0.0, 0.0)
    ox = min(min(w.x1, w.x2) for w in walls)
    oy = min(min(w.y1, w.y2) for w in walls)
    out = [Wall(w.wall_id, round(w.x1 - ox, 3), round(w.y1 - oy, 3), round(w.x2 - ox, 3),
                round(w.y2 - oy, 3), w.length, w.thickness, w.line_a, w.line_b) for w in walls]
    return out, (round(ox, 4), round(oy, 4))

"""
package.py  (المرحلة 4)
----------------------
يجمّع كل ما يحتاجه المستخدم لـ Revit في ملف zip واحد:
    - ملف Excel (الجدران + الفتحات)
    - ملف Dynamo (ahmednah.dyn)
    - تعليمات قصيرة
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

DYN_PATH = Path(__file__).resolve().parent.parent / "dynamo" / "ahmednah_walls.dyn"

INSTRUCTIONS = """ahmednah - طريقة الاستخدام في Revit
====================================

1. فك ضغط هذا الملف في أي مجلد على جهازك.
2. افتح Revit ثم مشروعاً جديداً (قالب Architectural) أو مشروعك.
3. Manage  ←  Dynamo  ←  Open  ←  ahmednah.dyn
4. في العقدة "1. Excel File" اضغط Browse واختر: {excel_name}
5. اضغط Run.

النتيجة: الجدران بارتفاع 3.5 م (يمكن تغييره من العقدة 2)، ثم الأبواب والشبابيك.

ملاحظات:
- يجب أن يحتوي المشروع على عائلة باب وعائلة شباك واحدة على الأقل.
- إذا فتحت كل الأبواب للجهة الخطأ: افتح كود عقدة "ahmednah - Doors & Windows"
  وغيّر SWING_TOWARD_FACING. وإذا كانت المفصلات في الطرف الخطأ: غيّر HINGE_TOWARD_HAND.
- إذا ظهرت رسالة عن محرك Python: زر يمين على عقدة البايثون واختر المحرك المتوفر
  (CPython3 أو PythonNet3).

الإحداثيات بالمتر، وأصلها (0,0) هو أسفل يسار المبنى.
"""


def build_revit_package(excel_bytes: bytes, base_name: str) -> bytes:
    excel_name = f"{base_name}_walls.xlsx"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(excel_name, excel_bytes)
        z.write(DYN_PATH, "ahmednah.dyn")
        z.writestr("اقرأني - README.txt", INSTRUCTIONS.format(excel_name=excel_name).encode("utf-8"))
    return buf.getvalue()

"""
wall_detector.py
----------------
تمييز الجدران من الخطوط المستخرجة.

القاعدة: أي خطين
  1) متوازيين (فرق الزاوية أقل من angle_tol درجة)
  2) المسافة العمودية بينهما بين min_thk و max_thk (افتراضياً 10–30 سم)
  3) متداخلين في الطول (إسقاط أحدهما على الآخر يعطي جزءاً مشتركاً كافياً)
يُعتبران وجهَي جدار واحد.

الجدار الناتج:
  - خط المحور (Centerline) في منتصف المسافة بين الخطين، على طول الجزء المشترك فقط
  - السماكة = المسافة العمودية بين الخطين
خط المحور هو بالضبط ما سنحتاجه في Revit (Wall.ByCurveAndHeight) في المرحلة الثانية.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from dataclasses import dataclass, asdict

from .pdf_extractor import Line


@dataclass
class Wall:
    wall_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    thickness: float
    line_a: int  # رقم الخط الأول المكوِّن للجدار
    line_b: int  # رقم الخط الثاني
    kind: str = "wall"  # "wall" أو "window" (المرحلة 3)

    def to_dict(self) -> dict:
        return asdict(self)


class _Seg:
    """خط مع خصائصه الهندسية الجاهزة للحساب."""

    def __init__(self, ln: Line, angle_tol: float):
        self.ln = ln
        dx, dy = ln.x2 - ln.x1, ln.y2 - ln.y1
        L = math.hypot(dx, dy)
        theta = math.degrees(math.atan2(dy, dx)) % 180.0
        # الخطوط الأفقية قد تأتي بزاوية 0.01 أو 179.99 → نوحّدها حول الصفر
        if theta >= 180.0 - angle_tol:
            theta -= 180.0
        self.theta = theta
        t = math.radians(theta)
        self.u = (math.cos(t), math.sin(t))   # اتجاه الخط
        self.n = (-math.sin(t), math.cos(t))  # العمودي عليه
        self.offset = self.n[0] * ln.x1 + self.n[1] * ln.y1  # بُعد الخط عن الأصل
        a = self.u[0] * ln.x1 + self.u[1] * ln.y1
        b = self.u[0] * ln.x2 + self.u[1] * ln.y2
        self.t0, self.t1 = min(a, b), max(a, b)  # امتداد الخط على محوره
        self.length = L
        self.used: list[tuple[float, float]] = []  # أجزاء استُخدمت في جدران سابقة

    def used_fraction(self, s: float, e: float) -> float:
        """نسبة الفترة [s,e] المستخدمة مسبقاً في جدار آخر."""
        if e <= s:
            return 1.0
        covered = 0.0
        for a, b in self.used:
            covered += max(0.0, min(b, e) - max(a, s))
        return min(1.0, covered / (e - s))


def detect_walls(
    lines: list[Line],
    min_thk: float = 0.10,
    max_thk: float = 0.30,
    angle_tol: float = 2.0,
    min_overlap: float = 0.20,
    min_line_length: float = 0.20,
    detect_windows: bool = True,
    window_len: tuple[float, float] = (0.40, 3.00),
) -> list[Wall]:
    """
    يرجع الجدران، ومعها الشبابيك بـ kind="window".

    الشباك في مخططات AutoCAD = خطان على وجهي الجدار + خط زجاج أو أكثر بينهما
    بنفس الطول تقريباً. لو لم نكتشفه أولاً، سيقترن خط الزجاج مع وجه الجدار
    ويظهر كجدار رفيع وهمي. لذلك نكتشف الشبابيك في جولة أولى ونحجز خطوطها.

    المعاملات (كلها بالمتر ما عدا الزاوية):
        min_thk, max_thk : حدود سماكة الجدار
        angle_tol        : السماحية في التوازي (درجات)
        min_overlap      : أقل طول مشترك بين الخطين ليُعتبرا جداراً
        min_line_length  : تجاهل الخطوط القصيرة جداً (رموز، تهشير، نصوص)
    """
    segs = [_Seg(l, angle_tol) for l in lines if l.length >= min_line_length]

    # 1) تجميع الخطوط حسب الزاوية (كل درجة سلة) لتسريع البحث
    buckets: dict[int, list[_Seg]] = defaultdict(list)
    for s in segs:
        buckets[int(math.floor(s.theta))].append(s)
    for b in buckets.values():
        b.sort(key=lambda s: s.offset)

    # 2) إيجاد كل الأزواج المرشحة
    candidates = []
    span = int(math.ceil(angle_tol))
    for A in segs:
        base = int(math.floor(A.theta))
        for k in range(base - span, base + span + 1):
            group = buckets.get(k)
            if not group:
                continue
            offsets = [g.offset for g in group]
            # نبحث فقط عن الخطوط التي offset تبعها أكبر (لتجنب تكرار الزوج)
            lo = bisect.bisect_left(offsets, A.offset + min_thk * 0.5)
            hi = bisect.bisect_right(offsets, A.offset + max_thk * 1.5)
            for B in group[lo:hi]:
                if B is A or abs(B.theta - A.theta) > angle_tol:
                    continue
                # المسافة العمودية الحقيقية: من منتصف B إلى امتداد A
                mx = (B.ln.x1 + B.ln.x2) / 2
                my = (B.ln.y1 + B.ln.y2) / 2
                d = abs(A.n[0] * mx + A.n[1] * my - A.offset)
                if not (min_thk - 1e-6 <= d <= max_thk + 1e-6):
                    continue
                # التداخل: نسقط B على محور A
                b0 = A.u[0] * B.ln.x1 + A.u[1] * B.ln.y1
                b1 = A.u[0] * B.ln.x2 + A.u[1] * B.ln.y2
                s, e = max(A.t0, min(b0, b1)), min(A.t1, max(b0, b1))
                if e - s < min_overlap:
                    continue
                candidates.append((d, -(e - s), A, B, s, e))

    walls: list[Wall] = []

    def project_on_b(A, B, s, e):
        pA_s = (A.u[0] * s + A.n[0] * A.offset, A.u[1] * s + A.n[1] * A.offset)
        pA_e = (A.u[0] * e + A.n[0] * A.offset, A.u[1] * e + A.n[1] * A.offset)
        tb_s = B.u[0] * pA_s[0] + B.u[1] * pA_s[1]
        tb_e = B.u[0] * pA_e[0] + B.u[1] * pA_e[1]
        return pA_s, pA_e, min(tb_s, tb_e), max(tb_s, tb_e)

    def make(A, B, d, s, e, pA_s, pA_e, kind):
        mx = (B.ln.x1 + B.ln.x2) / 2
        my = (B.ln.y1 + B.ln.y2) / 2
        side = 1.0 if (A.n[0] * mx + A.n[1] * my - A.offset) > 0 else -1.0
        h = side * d / 2
        return Wall(
            wall_id=len(walls) + 1,
            x1=round(pA_s[0] + A.n[0] * h, 3), y1=round(pA_s[1] + A.n[1] * h, 3),
            x2=round(pA_e[0] + A.n[0] * h, 3), y2=round(pA_e[1] + A.n[1] * h, 3),
            length=round(e - s, 3), thickness=round(d, 3),
            line_a=A.ln.id, line_b=B.ln.id, kind=kind,
        )

    # 3) الشبابيك أولاً: زوج متوازي وبينه خط (أو أكثر) يغطي معظم طوله
    if detect_windows:
        for d, _, A, B, s, e in sorted(candidates, key=lambda c: -c[0]):
            if not (window_len[0] <= e - s <= window_len[1]):
                continue
            if A.used_fraction(s, e) > 0.1:
                continue
            inner = []
            for k in range(int(math.floor(A.theta)) - span, int(math.floor(A.theta)) + span + 1):
                for C in buckets.get(k, []):
                    if C is A or C is B or abs(C.theta - A.theta) > angle_tol:
                        continue
                    mx, my = (C.ln.x1 + C.ln.x2) / 2, (C.ln.y1 + C.ln.y2) / 2
                    off = A.n[0] * mx + A.n[1] * my - A.offset
                    if not (0.01 < abs(off) < d - 0.01):
                        continue
                    c0 = A.u[0] * C.ln.x1 + A.u[1] * C.ln.y1
                    c1 = A.u[0] * C.ln.x2 + A.u[1] * C.ln.y2
                    ov = min(e, max(c0, c1)) - max(s, min(c0, c1))
                    if ov >= 0.7 * (e - s):
                        inner.append(C)
            if not inner:
                continue
            pA_s, pA_e, bs, be = project_on_b(A, B, s, e)
            if B.used_fraction(bs, be) > 0.1:
                continue
            A.used.append((s, e))
            B.used.append((bs, be))
            for C in inner:  # خطوط الزجاج محجوزة بالكامل
                C.used.append((C.t0 - 1, C.t1 + 1))
            walls.append(make(A, B, d, s, e, pA_s, pA_e, "window"))

    # 4) الجدران: الأقرب أولاً، ثم الأطول تداخلاً.
    #    كل جزء من الخط يُستخدم مرة واحدة فقط (الخط الطويل الخارجي يمكن أن
    #    يشكّل عدة جدران مع عدة خطوط داخلية قصيرة بسبب فتحات الأبواب).
    candidates.sort(key=lambda c: (round(c[0], 3), c[1]))
    for d, _, A, B, s, e in candidates:
        pA_s, pA_e, bs, be = project_on_b(A, B, s, e)
        if A.used_fraction(s, e) > 0.5 or B.used_fraction(bs, be) > 0.5:
            continue
        A.used.append((s, e))
        B.used.append((bs, be))
        walls.append(make(A, B, d, s, e, pA_s, pA_e, "wall"))
    return walls

"""
openings.py  (المرحلة 3)
-----------------------
من قطع الجدران والشبابيك إلى: جدران مستضيفة (Host Walls) + فتحات (أبواب/شبابيك).

لماذا ندمج؟
  في PDF الجدار الذي فيه باب يظهر كقطعتين بينهما فراغ. لكن في Revit الباب
  والشباك FamilyInstance "مستضاف" داخل جدار، والجدار يجب أن يكون مستمراً
  عبر الفتحة، والعنصر نفسه هو الذي يقصّ الفتحة. لذلك:

  1) نجمع القطع المتسامتة (نفس الاتجاه + نفس خط المحور + نفس السماكة).
  2) نرتبها على المحور، والفراغ بين قطعتين (0.5–2.5 م) = فتحة،
     بشرط ألا يقطع الفراغَ جدارٌ عمودي (وإلا فهو تقاطع وليس فتحة).
  3) التصنيف:
       قطعة نوعها window          ← شباك (Window)
       فراغ بجانبه قوس فتح        ← باب (Door)، ومن القوس نعرف جهة الفتح والمفصلة
       فراغ بدون قوس              ← فتحة فارغة (Opening)
  4) كل سلسلة متصلة تصبح جداراً واحداً من أول قطعة إلى آخر قطعة.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from .wall_detector import Wall
from .wall_joiner import _intersect


@dataclass
class Opening:
    opening_id: int
    kind: str           # Door / Window / Opening
    host_wall_id: int
    x: float            # مركز الفتحة على محور الجدار
    y: float
    width: float
    wall_thickness: float
    swing_side: int     # للأبواب: +1 يسار اتجاه الجدار (X1→X2)، -1 يمينه، 0 غير معروف
    hinge_at: str       # للأبواب: "start" المفصلة جهة (X1,Y1)، "end" جهة (X2,Y2)، "double" بابان
    leaves: int         # عدد الضلف

    def to_dict(self):
        return asdict(self)


class _Ax:
    """محور قطعة: اتجاه u، عمودي n، بُعد c، وامتداد [t0,t1]."""

    def __init__(self, w: Wall):
        self.w = w
        dx, dy = w.x2 - w.x1, w.y2 - w.y1
        L = math.hypot(dx, dy)
        th = math.atan2(dy, dx) % math.pi
        if th >= math.pi - math.radians(2):
            th -= math.pi
        self.th = th
        self.u = (math.cos(th), math.sin(th))
        self.n = (-self.u[1], self.u[0])
        self.c = self.n[0] * w.x1 + self.n[1] * w.y1
        a = self.u[0] * w.x1 + self.u[1] * w.y1
        b = self.u[0] * w.x2 + self.u[1] * w.y2
        self.t0, self.t1 = min(a, b), max(a, b)

    def point(self, t, c=None):
        c = self.c if c is None else c
        return (self.u[0] * t + self.n[0] * c, self.u[1] * t + self.n[1] * c)


def _gap_blocked(ax: _Ax, c: float, gs: float, ge: float, others: list[_Ax]) -> bool:
    """هل يقطع جدارٌ آخر (غير موازٍ) الفراغ بين gs و ge؟"""
    p1, p2 = ax.point(gs, c), ax.point(ge, c)
    for o in others:
        if abs(math.sin(o.th - ax.th)) < math.sin(math.radians(10)):
            continue
        P = _intersect(p1, p2, (o.w.x1, o.w.y1), (o.w.x2, o.w.y2))
        if P is None:
            continue
        t = ax.u[0] * P[0] + ax.u[1] * P[1]
        to = o.u[0] * P[0] + o.u[1] * P[1]
        if gs + 0.02 < t < ge - 0.02 and o.t0 - 0.02 <= to <= o.t1 + 0.02:
            return True
    return False


def _door_info(ax: _Ax, c: float, gs: float, ge: float, thk: float, arcs):
    """يبحث عن أقواس فتح قرب الفراغ. يرجع (عدد الأقواس, جهة الفتح, المفصلة)."""
    width = ge - gs
    found = []
    for arc in arcs:
        ts = [ax.u[0] * x + ax.u[1] * y for x, y in arc]
        offs = [ax.n[0] * x + ax.n[1] * y - c for x, y in arc]
        tm = sum(ts) / len(ts)
        if not (gs - 0.05 <= tm <= ge + 0.05):
            continue
        if max(abs(o) for o in offs) > width + thk + 0.1:
            continue
        found.append((ts, offs))
    if not found:
        return 0, 0, ""

    side = 1 if sum(sum(o) for _, o in found) > 0 else -1
    if len(found) >= 2:
        return len(found), side, "double"
    ts, offs = found[0]
    # طرف القوس الأبعد عن الجدار = طرف الضلفة المفتوحة، وهو فوق المفصلة
    i_tip = 0 if abs(offs[0]) > abs(offs[-1]) else len(offs) - 1
    t_tip = ts[i_tip]
    hinge_t = gs if abs(t_tip - gs) < abs(t_tip - ge) else ge
    return 1, side, ("start" if hinge_t == gs else "end")  # نسبةً لاتجاه u


def build_hosts_and_openings(segments: list[Wall], arcs, gap_range=(0.5, 2.5),
                             axis_tol=0.03, thk_tol=0.03):
    """
    segments: الجدران (kind=wall) والشبابيك (kind=window) بعد وصل الزوايا
    arcs    : أقواس بيزيه من المخطط
    يرجع (host_walls, openings)
    """
    axes = [_Ax(w) for w in segments]
    walls_only = [a for a in axes if a.w.kind == "wall"]

    # 1) تجميع القطع المتسامتة
    groups: list[list[_Ax]] = []
    for a in sorted(axes, key=lambda a: (round(a.th, 2), a.c)):
        for g in groups:
            r = g[0]
            if (abs(a.th - r.th) <= math.radians(2) and abs(a.c - r.c) <= axis_tol
                    and abs(a.w.thickness - r.w.thickness) <= thk_tol):
                g.append(a)
                break
        else:
            groups.append([a])

    hosts: list[Wall] = []
    openings: list[Opening] = []

    def flush(run, run_openings, ref: _Ax):
        t0 = min(a.t0 for a in run)
        t1 = max(a.t1 for a in run)
        c = sum(a.c * (a.t1 - a.t0) for a in run) / sum(a.t1 - a.t0 for a in run)
        thk = max(a.w.thickness for a in run)
        (x1, y1), (x2, y2) = ref.point(t0, c), ref.point(t1, c)
        hid = len(hosts) + 1
        hosts.append(Wall(hid, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3),
                          round(t1 - t0, 3), thk, run[0].w.line_a, run[-1].w.line_b))
        # اتجاه الجدار في Excel هو اتجاه u (من t0 إلى t1)، فجهة الفتح والمفصلة كما حسبناهما
        for kind, tc, width, side, hinge, leaves in run_openings:
            px, py = ref.point(tc, c)
            openings.append(Opening(len(openings) + 1, kind, hid, round(px, 3), round(py, 3),
                                    round(width, 3), thk, side, hinge, leaves))

    for g in groups:
        g.sort(key=lambda a: a.t0)
        ref = g[0]
        run, run_ops = [g[0]], []
        if g[0].w.kind == "window":
            run_ops.append(("Window", (g[0].t0 + g[0].t1) / 2, g[0].t1 - g[0].t0, 0, "", 1))
        end = g[0].t1
        for a in g[1:]:
            gap = a.t0 - end
            c = ref.c
            thk = max(x.w.thickness for x in run)
            if gap > gap_range[1] or (gap > 0.05 and _gap_blocked(ref, c, end, a.t0, walls_only)):
                flush(run, run_ops, ref)
                run, run_ops = [a], []
            else:
                if gap >= gap_range[0]:
                    n, side, hinge = _door_info(ref, c, end, a.t0, thk, arcs)
                    kind = "Door" if n else "Opening"
                    run_ops.append((kind, (end + a.t0) / 2, gap, side, hinge, max(n, 1)))
                run.append(a)
            if a.w.kind == "window":
                run_ops.append(("Window", (a.t0 + a.t1) / 2, a.t1 - a.t0, 0, "", 1))
            end = max(end, a.t1)
        flush(run, run_ops, ref)

    return hosts, openings


def shift_openings(openings: list[Opening], offset):
    ox, oy = offset
    for o in openings:
        o.x, o.y = round(o.x - ox, 3), round(o.y - oy, 3)
    return openings

"""
excel_exporter.py
-----------------
حفظ الجدران (والخطوط الخام للمراجعة) في ملف Excel.
الورقة الأولى "Walls" هي التي سيقرأها Dynamo في المرحلة الثانية،
لذلك أسماء الأعمدة فيها بالإنجليزية وثابتة.
"""

from __future__ import annotations

import io

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from .pdf_extractor import Line
from .wall_detector import Wall

WALL_COLUMNS = {
    "wall_id": "Wall_ID",
    "x1": "X1",
    "y1": "Y1",
    "x2": "X2",
    "y2": "Y2",
    "length": "Length_m",
    "thickness": "Thickness_m",
}


def walls_dataframe(walls: list[Wall]) -> pd.DataFrame:
    df = pd.DataFrame([w.to_dict() for w in walls], columns=list(WALL_COLUMNS) + ["line_a", "line_b"])
    return df[list(WALL_COLUMNS)].rename(columns=WALL_COLUMNS)


OPENING_COLUMNS = {
    "opening_id": "Opening_ID",
    "kind": "Type",
    "host_wall_id": "Host_Wall_ID",
    "x": "X",
    "y": "Y",
    "width": "Width_m",
    "wall_thickness": "Wall_Thickness_m",
    "swing_side": "Swing_Side",
    "hinge_at": "Hinge_At",
    "leaves": "Leaves",
}


def openings_dataframe(openings) -> pd.DataFrame:
    df = pd.DataFrame([o.to_dict() for o in openings], columns=list(OPENING_COLUMNS))
    return df.rename(columns=OPENING_COLUMNS)


def lines_dataframe(lines: list[Line]) -> pd.DataFrame:
    df = pd.DataFrame([l.to_dict() for l in lines])
    if df.empty:
        return df
    return df[["id", "x1", "y1", "x2", "y2", "length", "stroke_width"]].rename(
        columns={"id": "Line_ID", "x1": "X1", "y1": "Y1", "x2": "X2", "y2": "Y2",
                 "length": "Length_m", "stroke_width": "Stroke_Width_m"}
    )


def export_to_excel(walls: list[Wall], lines: list[Line], path: str | None = None,
                    meta: dict | None = None, openings=None) -> bytes:
    """
    يكتب الملف إلى path إن أُعطي، ويرجع محتواه bytes دائماً (لزر التحميل في الواجهة).
    meta: معلومات إضافية (المقياس، إزاحة الأصل...) تُحفظ في ورقة Info.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        walls_dataframe(walls).to_excel(xw, sheet_name="Walls", index=False)
        openings_dataframe(openings or []).to_excel(xw, sheet_name="Openings", index=False)
        lines_dataframe(lines).to_excel(xw, sheet_name="Lines", index=False)
        info = {"units": "meters", **(meta or {})}
        pd.DataFrame({"Key": list(info), "Value": [str(v) for v in info.values()]}).to_excel(
            xw, sheet_name="Info", index=False)

        header_fill = PatternFill("solid", fgColor="1F3A5F")
        for ws in xw.book.worksheets:
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 14
            ws.freeze_panes = "A2"

    data = buf.getvalue()
    if path:
        with open(path, "wb") as f:
            f.write(data)
    return data

"""
pipeline.py
-----------
المسار الكامل في دالة واحدة، تستخدمها الواجهة وسطر الأوامر معاً:
PDF → خطوط + أقواس → جدران + شبابيك → وصل الزوايا → دمج الجدران المستضيفة + الفتحات → نقل الأصل
"""

from __future__ import annotations

from .pdf_extractor import extract_lines
from .wall_detector import detect_walls
from .wall_joiner import join_walls, normalize_origin
from .openings import build_hosts_and_openings, shift_openings


def run(pdf, page_number=0, scale=100.0, min_thk=0.10, max_thk=0.30, angle_tol=2.0,
        min_overlap=0.20, min_line_length=0.20, join=True, normalize=True, openings=True):
    lines, info = extract_lines(pdf, page_number=page_number, scale=scale, min_length_m=0.01)
    segs = detect_walls(lines, min_thk=min_thk, max_thk=max_thk, angle_tol=angle_tol,
                        min_overlap=min_overlap, min_line_length=min_line_length,
                        detect_windows=openings)
    walls = [w for w in segs if w.kind == "wall"]
    windows = [w for w in segs if w.kind == "window"]

    if join:
        walls = join_walls(walls)

    ops = []
    if openings:
        walls, ops = build_hosts_and_openings(walls + windows, info["arcs"])

    offset = (0.0, 0.0)
    if normalize:
        walls, offset = normalize_origin(walls)
        shift_openings(ops, offset)

    meta = {"scale": f"1:{scale:g}", "page": page_number + 1,
            "origin_offset_x": offset[0], "origin_offset_y": offset[1],
            "corners_joined": join}
    return lines, walls, ops, info, offset, meta

{
  "Uuid": "7b59e4b8-1054-455f-8fad-6b27a608ea9a",
  "IsCustomNode": false,
  "Description": "ahmednah - walls, doors and windows from Excel",
  "Name": "ahmednah_walls",
  "ElementResolver": {
    "ResolutionMap": {}
  },
  "Inputs": [],
  "Outputs": [],
  "Nodes": [
    {
      "ConcreteType": "CoreNodeModels.Input.Filename, CoreNodeModels",
      "NodeType": "ExtensionNode",
      "Id": "636ac9fb479f4addb5c3b1bc9e30e46d",
      "Inputs": [],
      "Outputs": [
        {
          "Id": "25a0b60873e84817a6c0b2ffd970586d",
          "Name": "",
          "Description": "File path",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Excel file from ahmednah",
      "HintPath": "",
      "InputValue": ""
    },
    {
      "ConcreteType": "CoreNodeModels.Input.DoubleInput, CoreNodeModels",
      "NodeType": "NumberInputNode",
      "Id": "362d25b1137d42c4bc70764d58200b56",
      "Inputs": [],
      "Outputs": [
        {
          "Id": "0f412ac6eefd45a49b31a396b36e98cd",
          "Name": "",
          "Description": "Double",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Wall height (m)",
      "NumberType": "Double",
      "InputValue": 3.5
    },
    {
      "ConcreteType": "CoreNodeModels.Input.StringInput, CoreNodeModels",
      "NodeType": "StringInputNode",
      "Id": "c0f2b724cea94593839661f898ad38d6",
      "Inputs": [],
      "Outputs": [
        {
          "Id": "0a6b495727e646119ecf883638fd9db5",
          "Name": "",
          "Description": "String",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Level name (empty = lowest)",
      "InputValue": ""
    },
    {
      "ConcreteType": "PythonNodeModels.PythonNode, PythonNodeModels",
      "NodeType": "PythonScriptNode",
      "Id": "07dd8bc26cb543c5951fb5de8a00d0dd",
      "Inputs": [
        {
          "Id": "ad0d0efb1e6e45729be42b64ae059ff6",
          "Name": "IN[0]",
          "Description": "Excel path",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "28618e4e960843ffbbff5bff6c44f081",
          "Name": "IN[1]",
          "Description": "Height m",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "c2c0b9fcf2ae4b38adaf61887cb00335",
          "Name": "IN[2]",
          "Description": "Level name",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Outputs": [
        {
          "Id": "017ccfa9116f47a29e7c07c015c66b04",
          "Name": "OUT",
          "Description": "Result of the python script",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "ahmednah: read Excel walls",
      "Code": "# -*- coding: utf-8 -*-\n\"\"\"\nahmednah - Dynamo Python Script (المرحلة الثانية)\n=================================================\nيُلصق داخل عقدة Python Script في Dynamo (يعمل على CPython3 و IronPython2).\n\nالمدخلات:\n    IN[0]  مسار ملف Excel الناتج من ahmednah (ورقة Walls)\n    IN[1]  ارتفاع الجدار بالمتر (مثلاً 3.5)\n    IN[2]  اسم المستوى (Level) — اتركه فارغاً لاستخدام أدنى مستوى في المشروع\n\nالمخرجات (قائمة من 5 عناصر):\n    OUT[0] curves      : خطوط محاور الجدران (Dynamo Lines)\n    OUT[1] wall_types  : نوع الجدار المناسب لكل خط حسب سماكته\n    OUT[2] level       : المستوى\n    OUT[3] height      : الارتفاع بوحدات Dynamo\n    OUT[4] report      : تقرير نصي\n\nهذه المخرجات تدخل مباشرة إلى عقدة Wall.ByCurveAndHeight في الـ Graph.\n\nملاحظة: لا نستخدم openpyxl لأنها غير موجودة داخل Dynamo.\nملف xlsx هو ملف zip فيه XML، فنقرؤه بمكتبات بايثون القياسية فقط.\n\"\"\"\n\nimport clr\nimport re\nimport zipfile\nimport xml.etree.ElementTree as ET\n\nclr.AddReference(\"ProtoGeometry\")\nfrom Autodesk.DesignScript.Geometry import Point, Line\n\nclr.AddReference(\"RevitNodes\")\nimport Revit\nclr.ImportExtensions(Revit.Elements)\nclr.ImportExtensions(Revit.GeometryConversion)\n\nclr.AddReference(\"RevitServices\")\nfrom RevitServices.Persistence import DocumentManager\nfrom RevitServices.Transactions import TransactionManager\n\nclr.AddReference(\"RevitAPI\")\nimport Autodesk.Revit.DB as DB\n\ndoc = DocumentManager.Instance.CurrentDBDocument\nFT_PER_M = 1.0 / 0.3048\n\n\n# ---------------------------------------------------------------------------\n# 1) قراءة ملف Excel بدون مكتبات خارجية\n# ---------------------------------------------------------------------------\nNS_M = \"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"\nNS_R = \"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"\n\n\ndef _col_index(ref):\n    letters = re.match(r\"([A-Z]+)\", ref).group(1)\n    n = 0\n    for ch in letters:\n        n = n * 26 + (ord(ch) - 64)\n    return n - 1\n\n\ndef read_xlsx_sheet(path, sheet_name):\n    z = zipfile.ZipFile(path)\n    names = z.namelist()\n\n    shared = []\n    if \"xl/sharedStrings.xml\" in names:\n        root = ET.fromstring(z.read(\"xl/sharedStrings.xml\"))\n        for si in root.findall(\"{%s}si\" % NS_M):\n            shared.append(\"\".join([t.text or \"\" for t in si.iter(\"{%s}t\" % NS_M)]))\n\n    wb = ET.fromstring(z.read(\"xl/workbook.xml\"))\n    rels = ET.fromstring(z.read(\"xl/_rels/workbook.xml.rels\"))\n    relmap = dict((r.get(\"Id\"), r.get(\"Target\")) for r in rels)\n\n    target = None\n    for sh in wb.find(\"{%s}sheets\" % NS_M):\n        if sh.get(\"name\") == sheet_name:\n            target = relmap[sh.get(\"{%s}id\" % NS_R)]\n    if target is None:\n        raise Exception(\"Sheet '%s' not found in Excel file\" % sheet_name)\n    target = target[1:] if target.startswith(\"/\") else \"xl/\" + target\n\n    sheet = ET.fromstring(z.read(target))\n    rows = []\n    for row in sheet.find(\"{%s}sheetData\" % NS_M):\n        cells = {}\n        for c in row:\n            t = c.get(\"t\")\n            if t == \"inlineStr\":\n                v = \"\".join([x.text or \"\" for x in c.iter(\"{%s}t\" % NS_M)])\n            else:\n                v_el = c.find(\"{%s}v\" % NS_M)\n                v = v_el.text if v_el is not None else None\n                if v is not None:\n                    if t == \"s\":\n                        v = shared[int(v)]\n                    elif t not in (\"str\", \"b\", \"e\"):\n                        v = float(v)\n            cells[_col_index(c.get(\"r\"))] = v\n        if cells:\n            rows.append([cells.get(i) for i in range(max(cells) + 1)])\n    z.close()\n    return rows\n\n\ndef read_walls(path):\n    rows = read_xlsx_sheet(path, \"Walls\")\n    header = [str(h).strip() for h in rows[0]]\n    need = [\"Wall_ID\", \"X1\", \"Y1\", \"X2\", \"Y2\", \"Thickness_m\"]\n    for n in need:\n        if n not in header:\n            raise Exception(\"Missing column '%s' in sheet Walls\" % n)\n    idx = dict((n, header.index(n)) for n in need)\n    walls = []\n    for r in rows[1:]:\n        try:\n            walls.append(dict((n, float(r[idx[n]])) for n in need))\n        except (TypeError, ValueError, IndexError):\n            continue  # صف فارغ أو ناقص\n    return walls\n\n\n# ---------------------------------------------------------------------------\n# 2) الوحدات: كم وحدة Dynamo في المتر؟\n#    Dynamo for Revit يقرأ الأرقام بوحدات المشروع (مم/سم/م/قدم)، لذلك نحسبها\n# ---------------------------------------------------------------------------\ndef dynamo_units_per_meter():\n    from Revit.GeometryConversion import UnitConverter\n    for spec in (\"SpecTypeId\", \"UnitType\"):\n        try:\n            if spec == \"SpecTypeId\":\n                f = UnitConverter.DynamoToHostFactor(DB.SpecTypeId.Length)  # Revit 2021+\n            else:\n                f = UnitConverter.DynamoToHostFactor(DB.UnitType.UT_Length)  # Revit 2020-\n            return FT_PER_M / f\n        except Exception:\n            pass\n    return 1.0  # احتياط: نفترض متر\n\n\n# ---------------------------------------------------------------------------\n# 3) المستوى\n# ---------------------------------------------------------------------------\ndef get_level(name):\n    levels = list(DB.FilteredElementCollector(doc).OfClass(DB.Level))\n    if not levels:\n        raise Exception(\"No levels in this Revit project\")\n    if name:\n        for l in levels:\n            if l.Name.strip().lower() == name.strip().lower():\n                return l\n        raise Exception(\"Level '%s' not found. Available: %s\" % (name, \", \".join([l.Name for l in levels])))\n    return sorted(levels, key=lambda l: l.Elevation)[0]\n\n\n# ---------------------------------------------------------------------------\n# 4) نوع الجدار حسب السماكة: نبحث عن نوع موجود، وإلا ننشئ واحداً\n# ---------------------------------------------------------------------------\ndef type_name(t):\n    try:\n        return t.Name\n    except Exception:\n        return t.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()\n\n\ndef get_or_create_wall_type(width_m, cache, created):\n    key = int(round(width_m * 1000))  # بالمليمتر\n    if key in cache:\n        return cache[key]\n\n    width_ft = width_m * FT_PER_M\n    wanted = \"ahmednah_%dmm\" % key\n    basics = [t for t in DB.FilteredElementCollector(doc).OfClass(DB.WallType)\n              if t.Kind == DB.WallKind.Basic]\n\n    found = None\n    for t in basics:                       # أ) نوع أنشأناه سابقاً بنفس الاسم\n        if type_name(t) == wanted:\n            found = t\n            break\n    if found is None:                      # ب) أي نوع موجود بنفس السماكة (±0.5 مم)\n        for t in basics:\n            if abs(t.Width - width_ft) < 0.5 / 304.8:\n                found = t\n                break\n    if found is None:                      # ج) ننسخ نوعاً بسيطاً ونعدّل سماكته\n        def score(t):\n            cs = t.GetCompoundStructure()\n            layers = cs.LayerCount if cs else 99\n            generic = 0 if \"generic\" in type_name(t).lower() else 1\n            return (layers, generic)\n        base = sorted(basics, key=score)[0]\n        found = base.Duplicate(wanted)\n        cs = found.GetCompoundStructure()\n        thick_i = max(range(cs.LayerCount), key=lambda i: cs.GetLayerWidth(i))\n        new_w = cs.GetLayerWidth(thick_i) + (width_ft - cs.GetWidth())\n        if new_w <= 0:\n            raise Exception(\"Cannot make wall type %s from '%s'\" % (wanted, type_name(base)))\n        cs.SetLayerWidth(thick_i, new_w)\n        found.SetCompoundStructure(cs)\n        created.append(wanted)\n\n    cache[key] = found\n    return found\n\n\n# ---------------------------------------------------------------------------\n# التنفيذ\n# ---------------------------------------------------------------------------\npath = IN[0]\nheight_m = float(IN[1]) if IN[1] else 3.5\nlevel_name = IN[2] if len(IN) > 2 and IN[2] else \"\"\n\nwalls = read_walls(path)\nk = dynamo_units_per_meter()\n\nTransactionManager.Instance.EnsureInTransaction(doc)\nlevel = get_level(level_name)\ncache, created = {}, []\ncurves, types = [], []\nskipped = 0\nfor w in walls:\n    p1 = Point.ByCoordinates(w[\"X1\"] * k, w[\"Y1\"] * k, 0)\n    p2 = Point.ByCoordinates(w[\"X2\"] * k, w[\"Y2\"] * k, 0)\n    if p1.DistanceTo(p2) < 0.05 * k:       # أقصر من 5 سم: Revit يرفضه\n        skipped += 1\n        continue\n    curves.append(Line.ByStartPointEndPoint(p1, p2))\n    types.append(get_or_create_wall_type(w[\"Thickness_m\"], cache, created).ToDSType(True))\nTransactionManager.Instance.TransactionTaskDone()\n\nreport = \"\\n\".join([\n    \"ahmednah - walls ready: %d (skipped %d)\" % (len(curves), skipped),\n    \"Level: %s | Height: %.2f m\" % (level.Name, height_m),\n    \"Dynamo units per meter: %g\" % k,\n    \"Wall types used: %s\" % \", \".join(sorted(set(type_name(t) for t in cache.values()))),\n    \"Wall types created: %s\" % (\", \".join(created) if created else \"none\"),\n])\n\nOUT = [curves, types, level.ToDSType(True), height_m * k, report]\n",
      "Engine": "CPython3",
      "EngineName": "CPython3",
      "VariableInputPorts": true
    },
    {
      "ConcreteType": "Dynamo.Graph.Nodes.CodeBlockNodeModel, DynamoCore",
      "NodeType": "CodeBlockNode",
      "Id": "25a816a7f6e84642a3497a4075d7d2c9",
      "Inputs": [
        {
          "Id": "cf2905e499594988aeceae1879d17aad",
          "Name": "o",
          "Description": "",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Outputs": [
        {
          "Id": "fc6efa1553a34a28a7887e880c4ddbab",
          "Name": "",
          "Description": "curves",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "4dbdefebec324989bf181d51049fd20b",
          "Name": "",
          "Description": "wall types",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "7d8b580e7abd4f099defcb54a9c493d0",
          "Name": "",
          "Description": "level",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "9fc2f9843efe435c970f54be69ee147e",
          "Name": "",
          "Description": "height",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "a0b2dd991c7c409a893254b936159e8e",
          "Name": "",
          "Description": "report",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Split outputs",
      "Code": "o[0];\no[1];\no[2];\no[3];\no[4];"
    },
    {
      "ConcreteType": "Dynamo.Graph.Nodes.ZeroTouch.DSFunction, DynamoCore",
      "NodeType": "FunctionNode",
      "Id": "a1b052af9f274bf9a5b1b02a57a85935",
      "Inputs": [
        {
          "Id": "880bca2610104f679a694a235923fb32",
          "Name": "curve",
          "Description": "Curve",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "bb47fb5c178e467581e4764e24a49c1b",
          "Name": "height",
          "Description": "double",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "907dec88521049138e043b573cbb5005",
          "Name": "level",
          "Description": "Level",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "c76d57a9e1bc4f68bda4cac45c2fa09e",
          "Name": "wallType",
          "Description": "WallType",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Outputs": [
        {
          "Id": "79cd765dc3dd432788f148a8835464cb",
          "Name": "Wall",
          "Description": "Wall",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Auto",
      "Description": "Create walls",
      "FunctionSignature": "Revit.Elements.Wall.ByCurveAndHeight@Autodesk.DesignScript.Geometry.Curve,double,Revit.Elements.Level,Revit.Elements.WallType"
    },
    {
      "ConcreteType": "CoreNodeModels.Watch, CoreNodeModels",
      "NodeType": "ExtensionNode",
      "Id": "0dca5f7de44c4decaaa2e81c725bd951",
      "Inputs": [
        {
          "Id": "27972d1fd70045d9b755de819c5d1611",
          "Name": "",
          "Description": "Node to show output from",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Outputs": [
        {
          "Id": "1574b578c76e4d01bac6bf7c411b3b2e",
          "Name": "",
          "Description": "Node output",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Report"
    },
    {
      "ConcreteType": "CoreNodeModels.Watch, CoreNodeModels",
      "NodeType": "ExtensionNode",
      "Id": "b88e871c006f43b781e3c09a7c1b1696",
      "Inputs": [
        {
          "Id": "3faefbdab4c1463e90aeb8779e673db1",
          "Name": "",
          "Description": "Node to show output from",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Outputs": [
        {
          "Id": "003499d890c4433c80cc3c75ebd66269",
          "Name": "",
          "Description": "Node output",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Walls"
    },
    {
      "ConcreteType": "CoreNodeModels.Input.StringInput, CoreNodeModels",
      "NodeType": "StringInputNode",
      "Id": "90f45476acda431e831ff3c3a9e7c679",
      "Inputs": [],
      "Outputs": [
        {
          "Id": "3f5d330ab96e4c1d92d9e8608c45eb17",
          "Name": "",
          "Description": "String",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Door family/type (optional)",
      "InputValue": ""
    },
    {
      "ConcreteType": "CoreNodeModels.Input.StringInput, CoreNodeModels",
      "NodeType": "StringInputNode",
      "Id": "e67942dcd3c74aeb96aad9e0674f7d04",
      "Inputs": [],
      "Outputs": [
        {
          "Id": "305b3af215dd451d82ef05f46ba03a89",
          "Name": "",
          "Description": "String",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Window family/type (optional)",
      "InputValue": ""
    },
    {
      "ConcreteType": "CoreNodeModels.Input.DoubleInput, CoreNodeModels",
      "NodeType": "NumberInputNode",
      "Id": "9f3a12cb43484f5282a9953edb19c857",
      "Inputs": [],
      "Outputs": [
        {
          "Id": "6a2f80d65b904f398adaeb7786a97faf",
          "Name": "",
          "Description": "Double",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Window sill height (m)",
      "NumberType": "Double",
      "InputValue": 0.9
    },
    {
      "ConcreteType": "CoreNodeModels.Input.DoubleInput, CoreNodeModels",
      "NodeType": "NumberInputNode",
      "Id": "049bb06c4dd04f7d9fa4c47e302fec07",
      "Inputs": [],
      "Outputs": [
        {
          "Id": "d1191aff709346d3bfc70313e2db142e",
          "Name": "",
          "Description": "Double",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Empty opening height (m)",
      "NumberType": "Double",
      "InputValue": 2.1
    },
    {
      "ConcreteType": "PythonNodeModels.PythonNode, PythonNodeModels",
      "NodeType": "PythonScriptNode",
      "Id": "96ad2f4fdb4e428cbba108e68a0219df",
      "Inputs": [
        {
          "Id": "e188a99250194d8d9c1197c8cdb35a22",
          "Name": "IN[0]",
          "Description": "Walls",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "3aa30831da604c0797cc5db2b1189ab8",
          "Name": "IN[1]",
          "Description": "Excel path",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "f5f1c80239b34d74a448f25bb148cc85",
          "Name": "IN[2]",
          "Description": "Door type",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "be2fd9fe7ea846ad8ad13d32d1234866",
          "Name": "IN[3]",
          "Description": "Window type",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "ed84d9f6de6b45b5b470f720ec5564f3",
          "Name": "IN[4]",
          "Description": "Sill m",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "6228ad2e8ac34b3084b6712f6565f1e1",
          "Name": "IN[5]",
          "Description": "Opening h m",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Outputs": [
        {
          "Id": "2804f8926a244686845c6519c20380c6",
          "Name": "OUT",
          "Description": "Result of the python script",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "ahmednah: doors & windows",
      "Code": "# -*- coding: utf-8 -*-\n\"\"\"\nahmednah - Dynamo Python Script (المرحلة الثالثة): الأبواب والشبابيك\n====================================================================\nيُلصق داخل عقدة Python Script ثانية، تأتي بعد Wall.ByCurveAndHeight.\n\nالمدخلات:\n    IN[0]  الجدران الناتجة من Wall.ByCurveAndHeight\n    IN[1]  مسار ملف Excel (نفس ملف المرحلة 2 — ورقة Openings)\n    IN[2]  نوع الباب (اختياري) مثل \"Single-Flush\" أو \"Single-Flush : 0915 x 2134mm\"\n    IN[3]  نوع الشباك (اختياري) مثل \"Fixed\"\n    IN[4]  ارتفاع جلسة الشباك بالمتر (افتراضي 0.9)\n    IN[5]  ارتفاع الفتحة الفارغة بالمتر (افتراضي 2.1)\n\nالعمل:\n    - لكل باب/شباك: يختار FamilySymbol بنفس العرض، وإن لم يجد ينسخ نوعاً ويضبط عرضه\n    - يضعه FamilyInstance مستضافاً في الجدار الصحيح (أقرب جدار للنقطة)\n    - يضبط جهة فتح الباب والمفصلة كما في المخطط، ويجعل وجه الشباك للخارج\n    - الفتحات بدون باب: Wall Opening مستطيلة\n    - عند إعادة التشغيل يحذف ما أنشأه سابقاً (معلَّم بـ Comments = ahmednah) فلا يتكرر\n\"\"\"\n\nimport clr\nimport re\nimport zipfile\nimport xml.etree.ElementTree as ET\n\nclr.AddReference(\"RevitServices\")\nfrom RevitServices.Persistence import DocumentManager\nfrom RevitServices.Transactions import TransactionManager\n\nclr.AddReference(\"RevitAPI\")\nimport Autodesk.Revit.DB as DB\nfrom Autodesk.Revit.DB.Structure import StructuralType\n\nclr.AddReference(\"RevitNodes\")\nimport Revit\nclr.ImportExtensions(Revit.Elements)\n\ndoc = DocumentManager.Instance.CurrentDBDocument\nFT = 1.0 / 0.3048     # متر → قدم (وحدة Revit الداخلية)\nTAG = \"ahmednah\"\n\n# ---------------------------------------------------------------------------\n# معايرة اتجاه الأبواب (مرة واحدة فقط):\n# عائلات الأبواب تختلف في تعريف الوجه (Facing) واليد (Hand).\n# الإعداد الافتراضي مناسب لعائلات Revit القياسية (Single-Flush):\n#   الباب يفتح عكس اتجاه FacingOrientation، والمفصلة عكس اتجاه HandOrientation.\n# إذا فتحت كل الأبواب للجهة الخطأ → غيّر SWING_TOWARD_FACING\n# إذا كانت كل المفصلات في الطرف الخطأ → غيّر HINGE_TOWARD_HAND\n# ---------------------------------------------------------------------------\nSWING_TOWARD_FACING = False\nHINGE_TOWARD_HAND = False\n\n\n# ---------------------------------------------------------------------------\n# قراءة Excel (نفس قارئ المرحلة 2 — مكتبات قياسية فقط)\n# ---------------------------------------------------------------------------\nNS_M = \"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"\nNS_R = \"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"\n\n\ndef _col_index(ref):\n    letters = re.match(r\"([A-Z]+)\", ref).group(1)\n    n = 0\n    for ch in letters:\n        n = n * 26 + (ord(ch) - 64)\n    return n - 1\n\n\ndef read_xlsx_sheet(path, sheet_name):\n    z = zipfile.ZipFile(path)\n    names = z.namelist()\n\n    shared = []\n    if \"xl/sharedStrings.xml\" in names:\n        root = ET.fromstring(z.read(\"xl/sharedStrings.xml\"))\n        for si in root.findall(\"{%s}si\" % NS_M):\n            shared.append(\"\".join([t.text or \"\" for t in si.iter(\"{%s}t\" % NS_M)]))\n\n    wb = ET.fromstring(z.read(\"xl/workbook.xml\"))\n    rels = ET.fromstring(z.read(\"xl/_rels/workbook.xml.rels\"))\n    relmap = dict((r.get(\"Id\"), r.get(\"Target\")) for r in rels)\n\n    target = None\n    for sh in wb.find(\"{%s}sheets\" % NS_M):\n        if sh.get(\"name\") == sheet_name:\n            target = relmap[sh.get(\"{%s}id\" % NS_R)]\n    if target is None:\n        raise Exception(\"Sheet '%s' not found in Excel file\" % sheet_name)\n    target = target[1:] if target.startswith(\"/\") else \"xl/\" + target\n\n    sheet = ET.fromstring(z.read(target))\n    rows = []\n    for row in sheet.find(\"{%s}sheetData\" % NS_M):\n        cells = {}\n        for c in row:\n            t = c.get(\"t\")\n            if t == \"inlineStr\":\n                v = \"\".join([x.text or \"\" for x in c.iter(\"{%s}t\" % NS_M)])\n            else:\n                v_el = c.find(\"{%s}v\" % NS_M)\n                v = v_el.text if v_el is not None else None\n                if v is not None:\n                    if t == \"s\":\n                        v = shared[int(v)]\n                    elif t not in (\"str\", \"b\", \"e\"):\n                        v = float(v)\n            cells[_col_index(c.get(\"r\"))] = v\n        if cells:\n            rows.append([cells.get(i) for i in range(max(cells) + 1)])\n    z.close()\n    return rows\n\n\ndef read_openings(path):\n    rows = read_xlsx_sheet(path, \"Openings\")\n    if len(rows) < 2:\n        return []\n    header = [str(h).strip() for h in rows[0]]\n    out = []\n    for r in rows[1:]:\n        r = r + [None] * (len(header) - len(r))\n        d = dict(zip(header, r))\n        try:\n            out.append({\n                \"id\": int(d[\"Opening_ID\"]), \"type\": str(d[\"Type\"]),\n                \"x\": float(d[\"X\"]), \"y\": float(d[\"Y\"]), \"width\": float(d[\"Width_m\"]),\n                \"thk\": float(d[\"Wall_Thickness_m\"] or 0.2),\n                \"swing\": int(float(d.get(\"Swing_Side\") or 0)),\n                \"hinge\": str(d.get(\"Hinge_At\") or \"\"),\n                \"leaves\": int(float(d.get(\"Leaves\") or 1)),\n            })\n        except (TypeError, ValueError, KeyError):\n            continue\n    return out\n\n\n# ---------------------------------------------------------------------------\n# أدوات\n# ---------------------------------------------------------------------------\ndef flatten(x):\n    if isinstance(x, (list, tuple)):\n        res = []\n        for i in x:\n            res.extend(flatten(i))\n        return res\n    return [x]\n\n\ndef ename(e):\n    try:\n        return e.Name\n    except Exception:\n        return e.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()\n\n\ndef full_name(sym):\n    return \"%s : %s\" % (sym.FamilyName, ename(sym))\n\n\ndef width_param(sym):\n    for bip in (\"DOOR_WIDTH\", \"WINDOW_WIDTH\", \"FAMILY_WIDTH_PARAM\", \"FURNITURE_WIDTH\"):\n        try:\n            p = sym.get_Parameter(getattr(DB.BuiltInParameter, bip))\n        except Exception:\n            p = None\n        if p is not None and p.StorageType == DB.StorageType.Double:\n            return p\n    for n in (\"Width\", \"width\", \"Rough Width\"):\n        p = sym.LookupParameter(n)\n        if p is not None and p.StorageType == DB.StorageType.Double:\n            return p\n    return None\n\n\ndef set_comment(el, text):\n    p = el.get_Parameter(DB.BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)\n    if p is not None and not p.IsReadOnly:\n        p.Set(text)\n\n\ndef get_comment(el):\n    p = el.get_Parameter(DB.BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)\n    return p.AsString() if p is not None else None\n\n\nclass SymbolPicker(object):\n    \"\"\"يختار (أو ينشئ) FamilySymbol بالعرض المطلوب لكل فئة.\"\"\"\n\n    def __init__(self, bic, wanted_name):\n        self.all = list(DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol).OfCategory(bic))\n        self.pool = self.all\n        if wanted_name:\n            w = wanted_name.strip().lower()\n            m = [s for s in self.all if w == full_name(s).lower() or w == ename(s).lower()\n                 or w == s.FamilyName.lower()]\n            if not m:\n                m = [s for s in self.all if w in full_name(s).lower()]\n            if not m:\n                raise Exception(\"Family type '%s' not found. Available: %s\" %\n                                (wanted_name, \"; \".join(sorted(set(full_name(s) for s in self.all)))))\n            self.pool = m\n        self.cache = {}\n        self.created = []\n        self.warnings = []\n\n    def get(self, width_m, leaves=1):\n        if not self.pool:\n            return None\n        key = (int(round(width_m * 1000)), leaves)\n        if key in self.cache:\n            return self.cache[key]\n        pool = self.pool\n        if leaves >= 2:\n            dbl = [s for s in pool if \"double\" in s.FamilyName.lower()]\n            pool = dbl or pool\n        target = width_m * FT\n        best = None\n        for s in pool:  # أ) نوع موجود بنفس العرض (±1 سم)\n            p = width_param(s)\n            if p is not None and abs(p.AsDouble() - target) < 0.01 * FT:\n                best = s\n                break\n        if best is None:  # ب) ننسخ نوعاً من نفس العائلة ونضبط عرضه\n            base = pool[0]\n            new_name = \"%s_%s_%dmm\" % (ename(base), TAG, key[0])\n            existing = [s for s in self.all if ename(s) == new_name and s.FamilyName == base.FamilyName]\n            if existing:\n                best = existing[0]\n            else:\n                best = base.Duplicate(new_name)\n                p = width_param(best)\n                if p is not None and not p.IsReadOnly:\n                    p.Set(target)\n                    self.created.append(full_name(best))\n                else:\n                    self.warnings.append(\"Width not editable in '%s' — used as is\" % full_name(base))\n                self.all.append(best)\n        if not best.IsActive:\n            best.Activate()\n            doc.Regenerate()\n        self.cache[key] = best\n        return best\n\n\ndef host_for(walls, pt, thk):\n    \"\"\"أقرب جدار للنقطة، بشرط أن تقع النقطة على امتداده.\"\"\"\n    best, best_d = None, None\n    for w in walls:\n        lc = w.Location\n        if not isinstance(lc, DB.LocationCurve):\n            continue\n        c = lc.Curve\n        res = c.Project(pt)\n        if res is None:\n            continue\n        d = res.XYZPoint.DistanceTo(DB.XYZ(pt.X, pt.Y, res.XYZPoint.Z))\n        if d < (thk / 2 + 0.05) * FT and (best_d is None or d < best_d):\n            best, best_d = w, d\n    return best\n\n\ndef wall_dir(w):\n    c = w.Location.Curve\n    v = c.GetEndPoint(1) - c.GetEndPoint(0)\n    return DB.XYZ(v.X, v.Y, 0).Normalize()\n\n\n# ---------------------------------------------------------------------------\n# التنفيذ\n# ---------------------------------------------------------------------------\nwalls = [w for w in flatten(UnwrapElement(IN[0])) if isinstance(w, DB.Wall)]\npath = IN[1]\ndoor_name = IN[2] if len(IN) > 2 and IN[2] else \"\"\nwindow_name = IN[3] if len(IN) > 3 and IN[3] else \"\"\nsill_m = float(IN[4]) if len(IN) > 4 and IN[4] is not None else 0.9\nopen_h_m = float(IN[5]) if len(IN) > 5 and IN[5] is not None else 2.1\n\n\n\ndef id_val(eid):  # Revit 2024+ يستخدم Value بدل IntegerValue\n    return eid.Value if hasattr(eid, \"Value\") else eid.IntegerValue\n\n\nops = read_openings(path)\nwall_ids = set(id_val(w.Id) for w in walls)\n\nTransactionManager.Instance.EnsureInTransaction(doc)\n\n# 1) حذف ما أنشأناه في تشغيل سابق\nold = []\nfor bic in (DB.BuiltInCategory.OST_Doors, DB.BuiltInCategory.OST_Windows):\n    for fi in DB.FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType():\n        if get_comment(fi) == TAG and fi.Host is not None and id_val(fi.Host.Id) in wall_ids:\n            old.append(fi.Id)\nfor op in DB.FilteredElementCollector(doc).OfClass(DB.Opening):\n    if op.Host is not None and id_val(op.Host.Id) in wall_ids:\n        old.append(op.Id)\nfor eid in old:\n    doc.Delete(eid)\n\n# 2) مركز المبنى (لنعرف أين \"الخارج\" عند توجيه الشبابيك)\nmids = [w.Location.Curve.Evaluate(0.5, True) for w in walls]\ncx = sum(p.X for p in mids) / max(len(mids), 1)\ncy = sum(p.Y for p in mids) / max(len(mids), 1)\n\ndoors = SymbolPicker(DB.BuiltInCategory.OST_Doors, door_name)\nwins = SymbolPicker(DB.BuiltInCategory.OST_Windows, window_name)\n\nplaced, errors, n_open = [], [], 0\nfor o in ops:\n    try:\n        pt = DB.XYZ(o[\"x\"] * FT, o[\"y\"] * FT, 0)\n        wall = host_for(walls, pt, o[\"thk\"])\n        if wall is None:\n            errors.append(\"#%d: no host wall found\" % o[\"id\"])\n            continue\n        level = doc.GetElement(wall.LevelId)\n        z = level.Elevation\n        d = wall_dir(wall)\n        pt = DB.XYZ(pt.X, pt.Y, z)\n\n        if o[\"type\"] == \"Opening\":\n            half = d.Multiply(o[\"width\"] * FT / 2)\n            doc.Create.NewOpening(wall, pt.Subtract(half), pt.Add(half).Add(DB.XYZ(0, 0, open_h_m * FT)))\n            n_open += 1\n            continue\n\n        picker = doors if o[\"type\"] == \"Door\" else wins\n        sym = picker.get(o[\"width\"], o[\"leaves\"])\n        if sym is None:\n            errors.append(\"#%d: no %s family loaded in project\" % (o[\"id\"], o[\"type\"]))\n            continue\n        inst = doc.Create.NewFamilyInstance(pt, sym, wall, level, StructuralType.NonStructural)\n        set_comment(inst, TAG)\n        if o[\"type\"] == \"Window\":\n            p = inst.get_Parameter(DB.BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM)\n            if p is not None and not p.IsReadOnly:\n                p.Set(sill_m * FT)\n        placed.append((inst, o, d))\n    except Exception as ex:\n        errors.append(\"#%d: %s\" % (o[\"id\"], ex))\n\n# 3) ضبط الاتجاهات (يحتاج Regenerate حتى تُحسب Facing/Hand)\ndoc.Regenerate()\nleft = lambda v: DB.XYZ(-v.Y, v.X, 0)\nfor inst, o, d in placed:\n    try:\n        facing = inst.FacingOrientation\n        if o[\"type\"] == \"Door\" and o[\"swing\"] != 0:\n            swing = left(d).Multiply(o[\"swing\"])\n            want = 1 if SWING_TOWARD_FACING else -1\n            if facing.DotProduct(swing) * want < 0:\n                inst.flipFacing()\n            if o[\"hinge\"] in (\"start\", \"end\"):\n                doc.Regenerate()\n                hinge = d.Negate() if o[\"hinge\"] == \"start\" else d\n                want = 1 if HINGE_TOWARD_HAND else -1\n                if inst.HandOrientation.DotProduct(hinge) * want < 0:\n                    inst.flipHand()\n        elif o[\"type\"] == \"Window\":\n            p = inst.Location.Point\n            outward = DB.XYZ(p.X - cx, p.Y - cy, 0)\n            n = left(d)\n            out_n = n if n.DotProduct(outward) > 0 else n.Negate()\n            if facing.DotProduct(out_n) < 0:\n                inst.flipFacing()\n    except Exception as ex:\n        errors.append(\"#%d orient: %s\" % (o[\"id\"], ex))\n\nTransactionManager.Instance.TransactionTaskDone()\n\nn_d = sum(1 for _, o, _ in placed if o[\"type\"] == \"Door\")\nn_w = sum(1 for _, o, _ in placed if o[\"type\"] == \"Window\")\nreport = [\n    \"ahmednah - openings in Excel: %d\" % len(ops),\n    \"Doors placed: %d | Windows placed: %d | Empty openings: %d\" % (n_d, n_w, n_open),\n    \"Removed from previous run: %d\" % len(old),\n    \"Door types: %s\" % (\", \".join(sorted(set(full_name(s) for s in doors.cache.values()))) or \"-\"),\n    \"Window types: %s\" % (\", \".join(sorted(set(full_name(s) for s in wins.cache.values()))) or \"-\"),\n    \"Types created: %s\" % (\", \".join(doors.created + wins.created) or \"none\"),\n]\nreport += doors.warnings + wins.warnings\nif errors:\n    report.append(\"ERRORS:\")\n    report += errors\n\nOUT = [[i.ToDSType(True) for i, _, _ in placed], \"\\n\".join(report)]\n",
      "Engine": "CPython3",
      "EngineName": "CPython3",
      "VariableInputPorts": true
    },
    {
      "ConcreteType": "Dynamo.Graph.Nodes.CodeBlockNodeModel, DynamoCore",
      "NodeType": "CodeBlockNode",
      "Id": "a225c7739cdd454f9392f8b6ac40b527",
      "Inputs": [
        {
          "Id": "d1d797efb1c343c78da0ea1f71e22ca3",
          "Name": "p",
          "Description": "",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Outputs": [
        {
          "Id": "fdffded984984d419222cec7fff15f7a",
          "Name": "",
          "Description": "instances",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        },
        {
          "Id": "c0356cc6bea14900b7c2035851a41e73",
          "Name": "",
          "Description": "report",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Split",
      "Code": "p[0];\np[1];"
    },
    {
      "ConcreteType": "CoreNodeModels.Watch, CoreNodeModels",
      "NodeType": "ExtensionNode",
      "Id": "6b064de696044ffaa5c6f2a4caab4067",
      "Inputs": [
        {
          "Id": "7a23a6ba64aa411ba2f6f4502e5c0b0e",
          "Name": "",
          "Description": "Node to show output from",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Outputs": [
        {
          "Id": "5b4ea1d2ecdb4f16a426b3d6f543e545",
          "Name": "",
          "Description": "Node output",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Openings report"
    },
    {
      "ConcreteType": "CoreNodeModels.Watch, CoreNodeModels",
      "NodeType": "ExtensionNode",
      "Id": "67d65412179e4648a56050aa3e6b5df0",
      "Inputs": [
        {
          "Id": "cdcd7920ae7f46b999adfac51f281f6a",
          "Name": "",
          "Description": "Node to show output from",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Outputs": [
        {
          "Id": "fcab26b6bba54e8f9681ab4de924c4d8",
          "Name": "",
          "Description": "Node output",
          "UsingDefaultValue": false,
          "Level": 2,
          "UseLevels": false,
          "KeepListStructure": false
        }
      ],
      "Replication": "Disabled",
      "Description": "Doors & windows"
    }
  ],
  "Connectors": [
    {
      "Start": "25a0b60873e84817a6c0b2ffd970586d",
      "End": "ad0d0efb1e6e45729be42b64ae059ff6",
      "Id": "d9c80669fc4e4541938ae2d4eed73641",
      "IsHidden": "False"
    },
    {
      "Start": "0f412ac6eefd45a49b31a396b36e98cd",
      "End": "28618e4e960843ffbbff5bff6c44f081",
      "Id": "0d76ed3f0bca44c2896bcf18237ac0ea",
      "IsHidden": "False"
    },
    {
      "Start": "0a6b495727e646119ecf883638fd9db5",
      "End": "c2c0b9fcf2ae4b38adaf61887cb00335",
      "Id": "b66f0e2fcc26408f99cf87f6edd0e763",
      "IsHidden": "False"
    },
    {
      "Start": "017ccfa9116f47a29e7c07c015c66b04",
      "End": "cf2905e499594988aeceae1879d17aad",
      "Id": "69614e7704b04b678bc0ec9546c06530",
      "IsHidden": "False"
    },
    {
      "Start": "fc6efa1553a34a28a7887e880c4ddbab",
      "End": "880bca2610104f679a694a235923fb32",
      "Id": "07516d2075d84d2eb4c46a491b3ffa9c",
      "IsHidden": "False"
    },
    {
      "Start": "9fc2f9843efe435c970f54be69ee147e",
      "End": "bb47fb5c178e467581e4764e24a49c1b",
      "Id": "3d75589d9ec445bcaf81a341a605b7cc",
      "IsHidden": "False"
    },
    {
      "Start": "7d8b580e7abd4f099defcb54a9c493d0",
      "End": "907dec88521049138e043b573cbb5005",
      "Id": "0bb3f050975148348b8799ba62514efb",
      "IsHidden": "False"
    },
    {
      "Start": "4dbdefebec324989bf181d51049fd20b",
      "End": "c76d57a9e1bc4f68bda4cac45c2fa09e",
      "Id": "7e58ccaae1404c459a5e278446bb05a4",
      "IsHidden": "False"
    },
    {
      "Start": "a0b2dd991c7c409a893254b936159e8e",
      "End": "27972d1fd70045d9b755de819c5d1611",
      "Id": "06349fa7430e46e595083f29e4653eef",
      "IsHidden": "False"
    },
    {
      "Start": "79cd765dc3dd432788f148a8835464cb",
      "End": "3faefbdab4c1463e90aeb8779e673db1",
      "Id": "5cefe80b7de44a11bdec54605e73e4fc",
      "IsHidden": "False"
    },
    {
      "Start": "79cd765dc3dd432788f148a8835464cb",
      "End": "e188a99250194d8d9c1197c8cdb35a22",
      "Id": "e3f48567887143baaa0fcb08d02fcd66",
      "IsHidden": "False"
    },
    {
      "Start": "25a0b60873e84817a6c0b2ffd970586d",
      "End": "3aa30831da604c0797cc5db2b1189ab8",
      "Id": "66951bc4bd0f496bbe36cb9f4e02039c",
      "IsHidden": "False"
    },
    {
      "Start": "3f5d330ab96e4c1d92d9e8608c45eb17",
      "End": "f5f1c80239b34d74a448f25bb148cc85",
      "Id": "f6c5e08d77f549cb8d1a507ff1163b24",
      "IsHidden": "False"
    },
    {
      "Start": "305b3af215dd451d82ef05f46ba03a89",
      "End": "be2fd9fe7ea846ad8ad13d32d1234866",
      "Id": "21ee98ae3ce94299ba6c5f72efe21d43",
      "IsHidden": "False"
    },
    {
      "Start": "6a2f80d65b904f398adaeb7786a97faf",
      "End": "ed84d9f6de6b45b5b470f720ec5564f3",
      "Id": "81de2dc5cacf444281c1d7d492b3c135",
      "IsHidden": "False"
    },
    {
      "Start": "d1191aff709346d3bfc70313e2db142e",
      "End": "6228ad2e8ac34b3084b6712f6565f1e1",
      "Id": "54843f59ea8543b794b222653139eacd",
      "IsHidden": "False"
    },
    {
      "Start": "2804f8926a244686845c6519c20380c6",
      "End": "d1d797efb1c343c78da0ea1f71e22ca3",
      "Id": "a9e9757736d349c095a5c841f1a5105f",
      "IsHidden": "False"
    },
    {
      "Start": "c0356cc6bea14900b7c2035851a41e73",
      "End": "7a23a6ba64aa411ba2f6f4502e5c0b0e",
      "Id": "fd1aa8bf75564aad9736ea5b12f202ca",
      "IsHidden": "False"
    },
    {
      "Start": "fdffded984984d419222cec7fff15f7a",
      "End": "cdcd7920ae7f46b999adfac51f281f6a",
      "Id": "0fffc969882847beaa7bb6f652939db4",
      "IsHidden": "False"
    }
  ],
  "Dependencies": [],
  "NodeLibraryDependencies": [],
  "Bindings": [],
  "View": {
    "Dynamo": {
      "ScaleFactor": 1.0,
      "HasRunWithoutCrash": true,
      "IsVisibleInDynamoLibrary": true,
      "Version": "2.13.1.3887",
      "RunType": "Manual",
      "RunPeriod": "1000"
    },
    "Camera": {
      "Name": "Background Preview",
      "EyeX": -17.0,
      "EyeY": 24.0,
      "EyeZ": 50.0,
      "LookX": 12.0,
      "LookY": -13.0,
      "LookZ": -58.0,
      "UpX": 0.0,
      "UpY": 1.0,
      "UpZ": 0.0
    },
    "NodeViews": [
      {
        "Id": "636ac9fb479f4addb5c3b1bc9e30e46d",
        "Name": "1. Excel File (ahmednah)",
        "IsSetAsInput": true,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 0,
        "Y": 0
      },
      {
        "Id": "362d25b1137d42c4bc70764d58200b56",
        "Name": "2. Wall Height (m)",
        "IsSetAsInput": true,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 0,
        "Y": 160
      },
      {
        "Id": "c0f2b724cea94593839661f898ad38d6",
        "Name": "3. Level Name (empty = lowest)",
        "IsSetAsInput": true,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 0,
        "Y": 300
      },
      {
        "Id": "07dd8bc26cb543c5951fb5de8a00d0dd",
        "Name": "ahmednah - Read Walls",
        "IsSetAsInput": false,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 420,
        "Y": 120
      },
      {
        "Id": "25a816a7f6e84642a3497a4075d7d2c9",
        "Name": "Split",
        "IsSetAsInput": false,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 720,
        "Y": 120
      },
      {
        "Id": "a1b052af9f274bf9a5b1b02a57a85935",
        "Name": "Wall.ByCurveAndHeight",
        "IsSetAsInput": false,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1000,
        "Y": 80
      },
      {
        "Id": "0dca5f7de44c4decaaa2e81c725bd951",
        "Name": "Report",
        "IsSetAsInput": false,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1000,
        "Y": 380
      },
      {
        "Id": "b88e871c006f43b781e3c09a7c1b1696",
        "Name": "Walls",
        "IsSetAsInput": false,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1380,
        "Y": 80
      },
      {
        "Id": "90f45476acda431e831ff3c3a9e7c679",
        "Name": "4. Door Type (empty = any)",
        "IsSetAsInput": true,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1000,
        "Y": 620
      },
      {
        "Id": "e67942dcd3c74aeb96aad9e0674f7d04",
        "Name": "5. Window Type (empty = any)",
        "IsSetAsInput": true,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1000,
        "Y": 740
      },
      {
        "Id": "9f3a12cb43484f5282a9953edb19c857",
        "Name": "6. Window Sill Height (m)",
        "IsSetAsInput": true,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1000,
        "Y": 860
      },
      {
        "Id": "049bb06c4dd04f7d9fa4c47e302fec07",
        "Name": "7. Empty Opening Height (m)",
        "IsSetAsInput": true,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1000,
        "Y": 980
      },
      {
        "Id": "96ad2f4fdb4e428cbba108e68a0219df",
        "Name": "ahmednah - Doors & Windows",
        "IsSetAsInput": false,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1420,
        "Y": 640
      },
      {
        "Id": "a225c7739cdd454f9392f8b6ac40b527",
        "Name": "Split",
        "IsSetAsInput": false,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1720,
        "Y": 640
      },
      {
        "Id": "6b064de696044ffaa5c6f2a4caab4067",
        "Name": "Openings Report",
        "IsSetAsInput": false,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1950,
        "Y": 760
      },
      {
        "Id": "67d65412179e4648a56050aa3e6b5df0",
        "Name": "Doors & Windows",
        "IsSetAsInput": false,
        "IsSetAsOutput": false,
        "Excluded": false,
        "ShowGeometry": true,
        "X": 1950,
        "Y": 560
      }
    ],
    "Annotations": [],
    "X": 40.0,
    "Y": 60.0,
    "Zoom": 0.8
  }
}
# -*- coding: utf-8 -*-
"""
ahmednah - Dynamo Python Script (المرحلة الثانية)
=================================================
يُلصق داخل عقدة Python Script في Dynamo (يعمل على CPython3 و IronPython2).

المدخلات:
    IN[0]  مسار ملف Excel الناتج من ahmednah (ورقة Walls)
    IN[1]  ارتفاع الجدار بالمتر (مثلاً 3.5)
    IN[2]  اسم المستوى (Level) — اتركه فارغاً لاستخدام أدنى مستوى في المشروع

المخرجات (قائمة من 5 عناصر):
    OUT[0] curves      : خطوط محاور الجدران (Dynamo Lines)
    OUT[1] wall_types  : نوع الجدار المناسب لكل خط حسب سماكته
    OUT[2] level       : المستوى
    OUT[3] height      : الارتفاع بوحدات Dynamo
    OUT[4] report      : تقرير نصي

هذه المخرجات تدخل مباشرة إلى عقدة Wall.ByCurveAndHeight في الـ Graph.

ملاحظة: لا نستخدم openpyxl لأنها غير موجودة داخل Dynamo.
ملف xlsx هو ملف zip فيه XML، فنقرؤه بمكتبات بايثون القياسية فقط.
"""

import clr
import re
import zipfile
import xml.etree.ElementTree as ET

clr.AddReference("ProtoGeometry")
from Autodesk.DesignScript.Geometry import Point, Line

clr.AddReference("RevitNodes")
import Revit
clr.ImportExtensions(Revit.Elements)
clr.ImportExtensions(Revit.GeometryConversion)

clr.AddReference("RevitServices")
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

clr.AddReference("RevitAPI")
import Autodesk.Revit.DB as DB

doc = DocumentManager.Instance.CurrentDBDocument
FT_PER_M = 1.0 / 0.3048


# ---------------------------------------------------------------------------
# 1) قراءة ملف Excel بدون مكتبات خارجية
# ---------------------------------------------------------------------------
NS_M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _col_index(ref):
    letters = re.match(r"([A-Z]+)", ref).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx_sheet(path, sheet_name):
    z = zipfile.ZipFile(path)
    names = z.namelist()

    shared = []
    if "xl/sharedStrings.xml" in names:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("{%s}si" % NS_M):
            shared.append("".join([t.text or "" for t in si.iter("{%s}t" % NS_M)]))

    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = dict((r.get("Id"), r.get("Target")) for r in rels)

    target = None
    for sh in wb.find("{%s}sheets" % NS_M):
        if sh.get("name") == sheet_name:
            target = relmap[sh.get("{%s}id" % NS_R)]
    if target is None:
        raise Exception("Sheet '%s' not found in Excel file" % sheet_name)
    target = target[1:] if target.startswith("/") else "xl/" + target

    sheet = ET.fromstring(z.read(target))
    rows = []
    for row in sheet.find("{%s}sheetData" % NS_M):
        cells = {}
        for c in row:
            t = c.get("t")
            if t == "inlineStr":
                v = "".join([x.text or "" for x in c.iter("{%s}t" % NS_M)])
            else:
                v_el = c.find("{%s}v" % NS_M)
                v = v_el.text if v_el is not None else None
                if v is not None:
                    if t == "s":
                        v = shared[int(v)]
                    elif t not in ("str", "b", "e"):
                        v = float(v)
            cells[_col_index(c.get("r"))] = v
        if cells:
            rows.append([cells.get(i) for i in range(max(cells) + 1)])
    z.close()
    return rows


def read_walls(path):
    rows = read_xlsx_sheet(path, "Walls")
    header = [str(h).strip() for h in rows[0]]
    need = ["Wall_ID", "X1", "Y1", "X2", "Y2", "Thickness_m"]
    for n in need:
        if n not in header:
            raise Exception("Missing column '%s' in sheet Walls" % n)
    idx = dict((n, header.index(n)) for n in need)
    walls = []
    for r in rows[1:]:
        try:
            walls.append(dict((n, float(r[idx[n]])) for n in need))
        except (TypeError, ValueError, IndexError):
            continue  # صف فارغ أو ناقص
    return walls


# ---------------------------------------------------------------------------
# 2) الوحدات: كم وحدة Dynamo في المتر؟
#    Dynamo for Revit يقرأ الأرقام بوحدات المشروع (مم/سم/م/قدم)، لذلك نحسبها
# ---------------------------------------------------------------------------
def dynamo_units_per_meter():
    from Revit.GeometryConversion import UnitConverter
    for spec in ("SpecTypeId", "UnitType"):
        try:
            if spec == "SpecTypeId":
                f = UnitConverter.DynamoToHostFactor(DB.SpecTypeId.Length)  # Revit 2021+
            else:
                f = UnitConverter.DynamoToHostFactor(DB.UnitType.UT_Length)  # Revit 2020-
            return FT_PER_M / f
        except Exception:
            pass
    return 1.0  # احتياط: نفترض متر


# ---------------------------------------------------------------------------
# 3) المستوى
# ---------------------------------------------------------------------------
def get_level(name):
    levels = list(DB.FilteredElementCollector(doc).OfClass(DB.Level))
    if not levels:
        raise Exception("No levels in this Revit project")
    if name:
        for l in levels:
            if l.Name.strip().lower() == name.strip().lower():
                return l
        raise Exception("Level '%s' not found. Available: %s" % (name, ", ".join([l.Name for l in levels])))
    return sorted(levels, key=lambda l: l.Elevation)[0]


# ---------------------------------------------------------------------------
# 4) نوع الجدار حسب السماكة: نبحث عن نوع موجود، وإلا ننشئ واحداً
# ---------------------------------------------------------------------------
def type_name(t):
    try:
        return t.Name
    except Exception:
        return t.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()


def get_or_create_wall_type(width_m, cache, created):
    key = int(round(width_m * 1000))  # بالمليمتر
    if key in cache:
        return cache[key]

    width_ft = width_m * FT_PER_M
    wanted = "ahmednah_%dmm" % key
    basics = [t for t in DB.FilteredElementCollector(doc).OfClass(DB.WallType)
              if t.Kind == DB.WallKind.Basic]

    found = None
    for t in basics:                       # أ) نوع أنشأناه سابقاً بنفس الاسم
        if type_name(t) == wanted:
            found = t
            break
    if found is None:                      # ب) أي نوع موجود بنفس السماكة (±0.5 مم)
        for t in basics:
            if abs(t.Width - width_ft) < 0.5 / 304.8:
                found = t
                break
    if found is None:                      # ج) ننسخ نوعاً بسيطاً ونعدّل سماكته
        def score(t):
            cs = t.GetCompoundStructure()
            layers = cs.LayerCount if cs else 99
            generic = 0 if "generic" in type_name(t).lower() else 1
            return (layers, generic)
        base = sorted(basics, key=score)[0]
        found = base.Duplicate(wanted)
        cs = found.GetCompoundStructure()
        thick_i = max(range(cs.LayerCount), key=lambda i: cs.GetLayerWidth(i))
        new_w = cs.GetLayerWidth(thick_i) + (width_ft - cs.GetWidth())
        if new_w <= 0:
            raise Exception("Cannot make wall type %s from '%s'" % (wanted, type_name(base)))
        cs.SetLayerWidth(thick_i, new_w)
        found.SetCompoundStructure(cs)
        created.append(wanted)

    cache[key] = found
    return found


# ---------------------------------------------------------------------------
# التنفيذ
# ---------------------------------------------------------------------------
path = IN[0]
height_m = float(IN[1]) if IN[1] else 3.5
level_name = IN[2] if len(IN) > 2 and IN[2] else ""

walls = read_walls(path)
k = dynamo_units_per_meter()

TransactionManager.Instance.EnsureInTransaction(doc)
level = get_level(level_name)
cache, created = {}, []
curves, types = [], []
skipped = 0
for w in walls:
    p1 = Point.ByCoordinates(w["X1"] * k, w["Y1"] * k, 0)
    p2 = Point.ByCoordinates(w["X2"] * k, w["Y2"] * k, 0)
    if p1.DistanceTo(p2) < 0.05 * k:       # أقصر من 5 سم: Revit يرفضه
        skipped += 1
        continue
    curves.append(Line.ByStartPointEndPoint(p1, p2))
    types.append(get_or_create_wall_type(w["Thickness_m"], cache, created).ToDSType(True))
TransactionManager.Instance.TransactionTaskDone()

report = "\n".join([
    "ahmednah - walls ready: %d (skipped %d)" % (len(curves), skipped),
    "Level: %s | Height: %.2f m" % (level.Name, height_m),
    "Dynamo units per meter: %g" % k,
    "Wall types used: %s" % ", ".join(sorted(set(type_name(t) for t in cache.values()))),
    "Wall types created: %s" % (", ".join(created) if created else "none"),
])

OUT = [curves, types, level.ToDSType(True), height_m * k, report]

"""
يبني ملف ahmednah_walls.dyn من ahmednah_walls.py
(إذا عدّلت كود بايثون، شغّل هذا السكربت لتحديث ملف Dynamo)

    python dynamo/build_dyn.py
"""

import json
import uuid
from pathlib import Path

HERE = Path(__file__).parent


def gid():
    return uuid.uuid4().hex


def port(name, desc=""):
    return {"Id": gid(), "Name": name, "Description": desc, "UsingDefaultValue": False,
            "Level": 2, "UseLevels": False, "KeepListStructure": False}


def node(concrete, node_type, inputs, outputs, desc="", replication="Disabled", **extra):
    n = {"ConcreteType": concrete, "NodeType": node_type, "Id": gid(), "Inputs": inputs,
         "Outputs": outputs, "Replication": replication, "Description": desc}
    n.update(extra)
    return n


def build():
    code = (HERE / "ahmednah_walls.py").read_text(encoding="utf-8")

    n_file = node("CoreNodeModels.Input.Filename, CoreNodeModels", "ExtensionNode", [],
                  [port("", "File path")], "Excel file from ahmednah", HintPath="", InputValue="")
    n_h = node("CoreNodeModels.Input.DoubleInput, CoreNodeModels", "NumberInputNode", [],
               [port("", "Double")], "Wall height (m)", NumberType="Double", InputValue=3.5)
    n_lvl = node("CoreNodeModels.Input.StringInput, CoreNodeModels", "StringInputNode", [],
                 [port("", "String")], "Level name (empty = lowest)", InputValue="")
    n_py = node("PythonNodeModels.PythonNode, PythonNodeModels", "PythonScriptNode",
                [port("IN[0]", "Excel path"), port("IN[1]", "Height m"), port("IN[2]", "Level name")],
                [port("OUT", "Result of the python script")], "ahmednah: read Excel walls",
                Code=code, Engine="CPython3", EngineName="CPython3", VariableInputPorts=True)
    n_cb = node("Dynamo.Graph.Nodes.CodeBlockNodeModel, DynamoCore", "CodeBlockNode",
                [port("o")], [port("", "curves"), port("", "wall types"), port("", "level"),
                              port("", "height"), port("", "report")], "Split outputs",
                Code="o[0];\no[1];\no[2];\no[3];\no[4];")
    n_wall = node("Dynamo.Graph.Nodes.ZeroTouch.DSFunction, DynamoCore", "FunctionNode",
                  [port("curve", "Curve"), port("height", "double"), port("level", "Level"),
                   port("wallType", "WallType")], [port("Wall", "Wall")],
                  "Create walls", replication="Auto",
                  FunctionSignature="Revit.Elements.Wall.ByCurveAndHeight@Autodesk.DesignScript."
                                    "Geometry.Curve,double,Revit.Elements.Level,Revit.Elements.WallType")
    n_watch = node("CoreNodeModels.Watch, CoreNodeModels", "ExtensionNode",
                   [port("", "Node to show output from")], [port("", "Node output")], "Report")
    n_watch2 = node("CoreNodeModels.Watch, CoreNodeModels", "ExtensionNode",
                    [port("", "Node to show output from")], [port("", "Node output")], "Walls")

    # ---- المرحلة 3: الأبواب والشبابيك
    code2 = (HERE / "ahmednah_openings.py").read_text(encoding="utf-8")
    n_door = node("CoreNodeModels.Input.StringInput, CoreNodeModels", "StringInputNode", [],
                  [port("", "String")], "Door family/type (optional)", InputValue="")
    n_win = node("CoreNodeModels.Input.StringInput, CoreNodeModels", "StringInputNode", [],
                 [port("", "String")], "Window family/type (optional)", InputValue="")
    n_sill = node("CoreNodeModels.Input.DoubleInput, CoreNodeModels", "NumberInputNode", [],
                  [port("", "Double")], "Window sill height (m)", NumberType="Double", InputValue=0.9)
    n_oh = node("CoreNodeModels.Input.DoubleInput, CoreNodeModels", "NumberInputNode", [],
                [port("", "Double")], "Empty opening height (m)", NumberType="Double", InputValue=2.1)
    n_py2 = node("PythonNodeModels.PythonNode, PythonNodeModels", "PythonScriptNode",
                 [port("IN[0]", "Walls"), port("IN[1]", "Excel path"), port("IN[2]", "Door type"),
                  port("IN[3]", "Window type"), port("IN[4]", "Sill m"), port("IN[5]", "Opening h m")],
                 [port("OUT", "Result of the python script")], "ahmednah: doors & windows",
                 Code=code2, Engine="CPython3", EngineName="CPython3", VariableInputPorts=True)
    n_cb2 = node("Dynamo.Graph.Nodes.CodeBlockNodeModel, DynamoCore", "CodeBlockNode",
                 [port("p")], [port("", "instances"), port("", "report")], "Split", Code="p[0];\np[1];")
    n_watch3 = node("CoreNodeModels.Watch, CoreNodeModels", "ExtensionNode",
                    [port("", "Node to show output from")], [port("", "Node output")], "Openings report")
    n_watch4 = node("CoreNodeModels.Watch, CoreNodeModels", "ExtensionNode",
                    [port("", "Node to show output from")], [port("", "Node output")], "Doors & windows")

    nodes = [n_file, n_h, n_lvl, n_py, n_cb, n_wall, n_watch, n_watch2,
             n_door, n_win, n_sill, n_oh, n_py2, n_cb2, n_watch3, n_watch4]

    def link(a, ai, b, bi):
        return {"Start": a["Outputs"][ai]["Id"], "End": b["Inputs"][bi]["Id"], "Id": gid(),
                "IsHidden": "False"}

    connectors = [
        link(n_file, 0, n_py, 0), link(n_h, 0, n_py, 1), link(n_lvl, 0, n_py, 2),
        link(n_py, 0, n_cb, 0),
        link(n_cb, 0, n_wall, 0), link(n_cb, 3, n_wall, 1), link(n_cb, 2, n_wall, 2),
        link(n_cb, 1, n_wall, 3),
        link(n_cb, 4, n_watch, 0), link(n_wall, 0, n_watch2, 0),
        link(n_wall, 0, n_py2, 0), link(n_file, 0, n_py2, 1), link(n_door, 0, n_py2, 2),
        link(n_win, 0, n_py2, 3), link(n_sill, 0, n_py2, 4), link(n_oh, 0, n_py2, 5),
        link(n_py2, 0, n_cb2, 0), link(n_cb2, 1, n_watch3, 0), link(n_cb2, 0, n_watch4, 0),
    ]

    views = []
    layout = {  # الاسم والموقع على اللوحة
        n_file["Id"]: ("1. Excel File (ahmednah)", 0, 0),
        n_h["Id"]: ("2. Wall Height (m)", 0, 160),
        n_lvl["Id"]: ("3. Level Name (empty = lowest)", 0, 300),
        n_py["Id"]: ("ahmednah - Read Walls", 420, 120),
        n_cb["Id"]: ("Split", 720, 120),
        n_wall["Id"]: ("Wall.ByCurveAndHeight", 1000, 80),
        n_watch["Id"]: ("Report", 1000, 380),
        n_watch2["Id"]: ("Walls", 1380, 80),
        n_door["Id"]: ("4. Door Type (empty = any)", 1000, 620),
        n_win["Id"]: ("5. Window Type (empty = any)", 1000, 740),
        n_sill["Id"]: ("6. Window Sill Height (m)", 1000, 860),
        n_oh["Id"]: ("7. Empty Opening Height (m)", 1000, 980),
        n_py2["Id"]: ("ahmednah - Doors & Windows", 1420, 640),
        n_cb2["Id"]: ("Split", 1720, 640),
        n_watch3["Id"]: ("Openings Report", 1950, 760),
        n_watch4["Id"]: ("Doors & Windows", 1950, 560),
    }
    for n in nodes:
        name, x, y = layout[n["Id"]]
        views.append({"Id": n["Id"], "Name": name, "IsSetAsInput": n in (n_file, n_h, n_lvl, n_door, n_win, n_sill, n_oh),
                      "IsSetAsOutput": False, "Excluded": False, "ShowGeometry": True, "X": x, "Y": y})

    graph = {
        "Uuid": str(uuid.uuid4()), "IsCustomNode": False,
        "Description": "ahmednah - walls, doors and windows from Excel",
        "Name": "ahmednah_walls", "ElementResolver": {"ResolutionMap": {}},
        "Inputs": [], "Outputs": [], "Nodes": nodes, "Connectors": connectors,
        "Dependencies": [], "NodeLibraryDependencies": [], "Bindings": [],
        "View": {
            "Dynamo": {"ScaleFactor": 1.0, "HasRunWithoutCrash": True, "IsVisibleInDynamoLibrary": True,
                       "Version": "2.13.1.3887", "RunType": "Manual", "RunPeriod": "1000"},
            "Camera": {"Name": "Background Preview", "EyeX": -17.0, "EyeY": 24.0, "EyeZ": 50.0,
                       "LookX": 12.0, "LookY": -13.0, "LookZ": -58.0, "UpX": 0.0, "UpY": 1.0, "UpZ": 0.0},
            "NodeViews": views, "Annotations": [], "X": 40.0, "Y": 60.0, "Zoom": 0.8,
        },
    }
    out = HERE / "ahmednah_walls.dyn"
    out.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    print("تم إنشاء:", out)


if __name__ == "__main__":
    build()

# -*- coding: utf-8 -*-
"""
ahmednah - Dynamo Python Script (المرحلة الثالثة): الأبواب والشبابيك
====================================================================
يُلصق داخل عقدة Python Script ثانية، تأتي بعد Wall.ByCurveAndHeight.

المدخلات:
    IN[0]  الجدران الناتجة من Wall.ByCurveAndHeight
    IN[1]  مسار ملف Excel (نفس ملف المرحلة 2 — ورقة Openings)
    IN[2]  نوع الباب (اختياري) مثل "Single-Flush" أو "Single-Flush : 0915 x 2134mm"
    IN[3]  نوع الشباك (اختياري) مثل "Fixed"
    IN[4]  ارتفاع جلسة الشباك بالمتر (افتراضي 0.9)
    IN[5]  ارتفاع الفتحة الفارغة بالمتر (افتراضي 2.1)

العمل:
    - لكل باب/شباك: يختار FamilySymbol بنفس العرض، وإن لم يجد ينسخ نوعاً ويضبط عرضه
    - يضعه FamilyInstance مستضافاً في الجدار الصحيح (أقرب جدار للنقطة)
    - يضبط جهة فتح الباب والمفصلة كما في المخطط، ويجعل وجه الشباك للخارج
    - الفتحات بدون باب: Wall Opening مستطيلة
    - عند إعادة التشغيل يحذف ما أنشأه سابقاً (معلَّم بـ Comments = ahmednah) فلا يتكرر
"""

import clr
import re
import zipfile
import xml.etree.ElementTree as ET

clr.AddReference("RevitServices")
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

clr.AddReference("RevitAPI")
import Autodesk.Revit.DB as DB
from Autodesk.Revit.DB.Structure import StructuralType

clr.AddReference("RevitNodes")
import Revit
clr.ImportExtensions(Revit.Elements)

doc = DocumentManager.Instance.CurrentDBDocument
FT = 1.0 / 0.3048     # متر → قدم (وحدة Revit الداخلية)
TAG = "ahmednah"

# ---------------------------------------------------------------------------
# معايرة اتجاه الأبواب (مرة واحدة فقط):
# عائلات الأبواب تختلف في تعريف الوجه (Facing) واليد (Hand).
# الإعداد الافتراضي مناسب لعائلات Revit القياسية (Single-Flush):
#   الباب يفتح عكس اتجاه FacingOrientation، والمفصلة عكس اتجاه HandOrientation.
# إذا فتحت كل الأبواب للجهة الخطأ → غيّر SWING_TOWARD_FACING
# إذا كانت كل المفصلات في الطرف الخطأ → غيّر HINGE_TOWARD_HAND
# ---------------------------------------------------------------------------
SWING_TOWARD_FACING = False
HINGE_TOWARD_HAND = False


# ---------------------------------------------------------------------------
# قراءة Excel (نفس قارئ المرحلة 2 — مكتبات قياسية فقط)
# ---------------------------------------------------------------------------
NS_M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _col_index(ref):
    letters = re.match(r"([A-Z]+)", ref).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx_sheet(path, sheet_name):
    z = zipfile.ZipFile(path)
    names = z.namelist()

    shared = []
    if "xl/sharedStrings.xml" in names:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("{%s}si" % NS_M):
            shared.append("".join([t.text or "" for t in si.iter("{%s}t" % NS_M)]))

    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = dict((r.get("Id"), r.get("Target")) for r in rels)

    target = None
    for sh in wb.find("{%s}sheets" % NS_M):
        if sh.get("name") == sheet_name:
            target = relmap[sh.get("{%s}id" % NS_R)]
    if target is None:
        raise Exception("Sheet '%s' not found in Excel file" % sheet_name)
    target = target[1:] if target.startswith("/") else "xl/" + target

    sheet = ET.fromstring(z.read(target))
    rows = []
    for row in sheet.find("{%s}sheetData" % NS_M):
        cells = {}
        for c in row:
            t = c.get("t")
            if t == "inlineStr":
                v = "".join([x.text or "" for x in c.iter("{%s}t" % NS_M)])
            else:
                v_el = c.find("{%s}v" % NS_M)
                v = v_el.text if v_el is not None else None
                if v is not None:
                    if t == "s":
                        v = shared[int(v)]
                    elif t not in ("str", "b", "e"):
                        v = float(v)
            cells[_col_index(c.get("r"))] = v
        if cells:
            rows.append([cells.get(i) for i in range(max(cells) + 1)])
    z.close()
    return rows


def read_openings(path):
    rows = read_xlsx_sheet(path, "Openings")
    if len(rows) < 2:
        return []
    header = [str(h).strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = r + [None] * (len(header) - len(r))
        d = dict(zip(header, r))
        try:
            out.append({
                "id": int(d["Opening_ID"]), "type": str(d["Type"]),
                "x": float(d["X"]), "y": float(d["Y"]), "width": float(d["Width_m"]),
                "thk": float(d["Wall_Thickness_m"] or 0.2),
                "swing": int(float(d.get("Swing_Side") or 0)),
                "hinge": str(d.get("Hinge_At") or ""),
                "leaves": int(float(d.get("Leaves") or 1)),
            })
        except (TypeError, ValueError, KeyError):
            continue
    return out


# ---------------------------------------------------------------------------
# أدوات
# ---------------------------------------------------------------------------
def flatten(x):
    if isinstance(x, (list, tuple)):
        res = []
        for i in x:
            res.extend(flatten(i))
        return res
    return [x]


def ename(e):
    try:
        return e.Name
    except Exception:
        return e.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()


def full_name(sym):
    return "%s : %s" % (sym.FamilyName, ename(sym))


def width_param(sym):
    for bip in ("DOOR_WIDTH", "WINDOW_WIDTH", "FAMILY_WIDTH_PARAM", "FURNITURE_WIDTH"):
        try:
            p = sym.get_Parameter(getattr(DB.BuiltInParameter, bip))
        except Exception:
            p = None
        if p is not None and p.StorageType == DB.StorageType.Double:
            return p
    for n in ("Width", "width", "Rough Width"):
        p = sym.LookupParameter(n)
        if p is not None and p.StorageType == DB.StorageType.Double:
            return p
    return None


def set_comment(el, text):
    p = el.get_Parameter(DB.BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
    if p is not None and not p.IsReadOnly:
        p.Set(text)


def get_comment(el):
    p = el.get_Parameter(DB.BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
    return p.AsString() if p is not None else None


class SymbolPicker(object):
    """يختار (أو ينشئ) FamilySymbol بالعرض المطلوب لكل فئة."""

    def __init__(self, bic, wanted_name):
        self.all = list(DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol).OfCategory(bic))
        self.pool = self.all
        if wanted_name:
            w = wanted_name.strip().lower()
            m = [s for s in self.all if w == full_name(s).lower() or w == ename(s).lower()
                 or w == s.FamilyName.lower()]
            if not m:
                m = [s for s in self.all if w in full_name(s).lower()]
            if not m:
                raise Exception("Family type '%s' not found. Available: %s" %
                                (wanted_name, "; ".join(sorted(set(full_name(s) for s in self.all)))))
            self.pool = m
        self.cache = {}
        self.created = []
        self.warnings = []

    def get(self, width_m, leaves=1):
        if not self.pool:
            return None
        key = (int(round(width_m * 1000)), leaves)
        if key in self.cache:
            return self.cache[key]
        pool = self.pool
        if leaves >= 2:
            dbl = [s for s in pool if "double" in s.FamilyName.lower()]
            pool = dbl or pool
        target = width_m * FT
        best = None
        for s in pool:  # أ) نوع موجود بنفس العرض (±1 سم)
            p = width_param(s)
            if p is not None and abs(p.AsDouble() - target) < 0.01 * FT:
                best = s
                break
        if best is None:  # ب) ننسخ نوعاً من نفس العائلة ونضبط عرضه
            base = pool[0]
            new_name = "%s_%s_%dmm" % (ename(base), TAG, key[0])
            existing = [s for s in self.all if ename(s) == new_name and s.FamilyName == base.FamilyName]
            if existing:
                best = existing[0]
            else:
                best = base.Duplicate(new_name)
                p = width_param(best)
                if p is not None and not p.IsReadOnly:
                    p.Set(target)
                    self.created.append(full_name(best))
                else:
                    self.warnings.append("Width not editable in '%s' — used as is" % full_name(base))
                self.all.append(best)
        if not best.IsActive:
            best.Activate()
            doc.Regenerate()
        self.cache[key] = best
        return best


def host_for(walls, pt, thk):
    """أقرب جدار للنقطة، بشرط أن تقع النقطة على امتداده."""
    best, best_d = None, None
    for w in walls:
        lc = w.Location
        if not isinstance(lc, DB.LocationCurve):
            continue
        c = lc.Curve
        res = c.Project(pt)
        if res is None:
            continue
        d = res.XYZPoint.DistanceTo(DB.XYZ(pt.X, pt.Y, res.XYZPoint.Z))
        if d < (thk / 2 + 0.05) * FT and (best_d is None or d < best_d):
            best, best_d = w, d
    return best


def wall_dir(w):
    c = w.Location.Curve
    v = c.GetEndPoint(1) - c.GetEndPoint(0)
    return DB.XYZ(v.X, v.Y, 0).Normalize()


# ---------------------------------------------------------------------------
# التنفيذ
# ---------------------------------------------------------------------------
walls = [w for w in flatten(UnwrapElement(IN[0])) if isinstance(w, DB.Wall)]
path = IN[1]
door_name = IN[2] if len(IN) > 2 and IN[2] else ""
window_name = IN[3] if len(IN) > 3 and IN[3] else ""
sill_m = float(IN[4]) if len(IN) > 4 and IN[4] is not None else 0.9
open_h_m = float(IN[5]) if len(IN) > 5 and IN[5] is not None else 2.1



def id_val(eid):  # Revit 2024+ يستخدم Value بدل IntegerValue
    return eid.Value if hasattr(eid, "Value") else eid.IntegerValue


ops = read_openings(path)
wall_ids = set(id_val(w.Id) for w in walls)

TransactionManager.Instance.EnsureInTransaction(doc)

# 1) حذف ما أنشأناه في تشغيل سابق
old = []
for bic in (DB.BuiltInCategory.OST_Doors, DB.BuiltInCategory.OST_Windows):
    for fi in DB.FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType():
        if get_comment(fi) == TAG and fi.Host is not None and id_val(fi.Host.Id) in wall_ids:
            old.append(fi.Id)
for op in DB.FilteredElementCollector(doc).OfClass(DB.Opening):
    if op.Host is not None and id_val(op.Host.Id) in wall_ids:
        old.append(op.Id)
for eid in old:
    doc.Delete(eid)

# 2) مركز المبنى (لنعرف أين "الخارج" عند توجيه الشبابيك)
mids = [w.Location.Curve.Evaluate(0.5, True) for w in walls]
cx = sum(p.X for p in mids) / max(len(mids), 1)
cy = sum(p.Y for p in mids) / max(len(mids), 1)

doors = SymbolPicker(DB.BuiltInCategory.OST_Doors, door_name)
wins = SymbolPicker(DB.BuiltInCategory.OST_Windows, window_name)

placed, errors, n_open = [], [], 0
for o in ops:
    try:
        pt = DB.XYZ(o["x"] * FT, o["y"] * FT, 0)
        wall = host_for(walls, pt, o["thk"])
        if wall is None:
            errors.append("#%d: no host wall found" % o["id"])
            continue
        level = doc.GetElement(wall.LevelId)
        z = level.Elevation
        d = wall_dir(wall)
        pt = DB.XYZ(pt.X, pt.Y, z)

        if o["type"] == "Opening":
            half = d.Multiply(o["width"] * FT / 2)
            doc.Create.NewOpening(wall, pt.Subtract(half), pt.Add(half).Add(DB.XYZ(0, 0, open_h_m * FT)))
            n_open += 1
            continue

        picker = doors if o["type"] == "Door" else wins
        sym = picker.get(o["width"], o["leaves"])
        if sym is None:
            errors.append("#%d: no %s family loaded in project" % (o["id"], o["type"]))
            continue
        inst = doc.Create.NewFamilyInstance(pt, sym, wall, level, StructuralType.NonStructural)
        set_comment(inst, TAG)
        if o["type"] == "Window":
            p = inst.get_Parameter(DB.BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(sill_m * FT)
        placed.append((inst, o, d))
    except Exception as ex:
        errors.append("#%d: %s" % (o["id"], ex))

# 3) ضبط الاتجاهات (يحتاج Regenerate حتى تُحسب Facing/Hand)
doc.Regenerate()
left = lambda v: DB.XYZ(-v.Y, v.X, 0)
for inst, o, d in placed:
    try:
        facing = inst.FacingOrientation
        if o["type"] == "Door" and o["swing"] != 0:
            swing = left(d).Multiply(o["swing"])
            want = 1 if SWING_TOWARD_FACING else -1
            if facing.DotProduct(swing) * want < 0:
                inst.flipFacing()
            if o["hinge"] in ("start", "end"):
                doc.Regenerate()
                hinge = d.Negate() if o["hinge"] == "start" else d
                want = 1 if HINGE_TOWARD_HAND else -1
                if inst.HandOrientation.DotProduct(hinge) * want < 0:
                    inst.flipHand()
        elif o["type"] == "Window":
            p = inst.Location.Point
            outward = DB.XYZ(p.X - cx, p.Y - cy, 0)
            n = left(d)
            out_n = n if n.DotProduct(outward) > 0 else n.Negate()
            if facing.DotProduct(out_n) < 0:
                inst.flipFacing()
    except Exception as ex:
        errors.append("#%d orient: %s" % (o["id"], ex))

TransactionManager.Instance.TransactionTaskDone()

n_d = sum(1 for _, o, _ in placed if o["type"] == "Door")
n_w = sum(1 for _, o, _ in placed if o["type"] == "Window")
report = [
    "ahmednah - openings in Excel: %d" % len(ops),
    "Doors placed: %d | Windows placed: %d | Empty openings: %d" % (n_d, n_w, n_open),
    "Removed from previous run: %d" % len(old),
    "Door types: %s" % (", ".join(sorted(set(full_name(s) for s in doors.cache.values()))) or "-"),
    "Window types: %s" % (", ".join(sorted(set(full_name(s) for s in wins.cache.values()))) or "-"),
    "Types created: %s" % (", ".join(doors.created + wins.created) or "none"),
]
report += doors.warnings + wins.warnings
if errors:
    report.append("ERRORS:")
    report += errors

OUT = [[i.ToDSType(True) for i, _, _ in placed], "\n".join(report)]


"""
يولّد مخططاً تجريبياً (sample_plan.pdf) لاختبار التطبيق إن لم يكن لديك ملف AutoCAD.
- غرفتان، جدران خارجية 25 سم، جدار داخلي 15 سم
- شباك في الجدار الجنوبي (خطا الوجهين + خط زجاج في المنتصف)
- باب مدخل في الجدار الجنوبي، وباب داخلي، كلاهما بقوس فتح
المقياس 1:100.   التشغيل:  python samples/make_sample.py
"""

from pathlib import Path

import pymupdf

SCALE = 100
M = 1000 / SCALE / (25.4 / 72)  # كم point في المتر على مقياس 1:100
KAPPA = 0.5523                   # لتقريب ربع دائرة بمنحنى بيزيه


def main():
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)  # A4 أفقي
    H = page.rect.height
    sh = page.new_shape()

    def P(x, y):  # متر (Y للأعلى) → PDF point (Y للأسفل)
        return pymupdf.Point(40 + x * M, H - 40 - y * M)

    def line(x1, y1, x2, y2):
        sh.draw_line(P(x1, y1), P(x2, y2))

    def door_swing(hx, hy, ux, uy, nx, ny, r):
        """مفصلة عند (hx,hy)، u: اتجاه الفتحة على طول الجدار، n: جهة الفتح."""
        tip = (hx + nx * r, hy + ny * r)
        latch = (hx + ux * r, hy + uy * r)
        line(hx, hy, *tip)  # ضلفة الباب
        sh.draw_bezier(P(*tip),
                       P(tip[0] + ux * r * KAPPA, tip[1] + uy * r * KAPPA),
                       P(latch[0] + nx * r * KAPPA, latch[1] + ny * r * KAPPA),
                       P(*latch))

    W, D, t, ti = 10.0, 7.0, 0.25, 0.15

    # --- الجدار الجنوبي: شباك 2.0→3.5 وباب مدخل 7.5→8.5
    for a, b in [(0, 2.0), (3.5, 7.5), (8.5, W)]:
        line(a, 0, b, 0)
    for a, b in [(t, 2.0), (3.5, 7.5), (8.5, W - t)]:
        line(a, t, b, t)
    for x in (2.0, 3.5, 7.5, 8.5):
        line(x, 0, x, t)  # أطراف الفتحات
    line(2.0, 0, 3.5, 0); line(2.0, t, 3.5, t)  # وجها الشباك
    line(2.0, t / 2, 3.5, t / 2)                # خط الزجاج
    door_swing(7.5, t, 1, 0, 0, 1, 1.0)          # باب المدخل يفتح للداخل

    # --- بقية الجدار الخارجي
    line(0, D, W, D);  line(t, D - t, W - t, D - t)  # شمالي
    line(0, 0, 0, D);  line(t, t, t, D - t)          # غربي
    line(W, 0, W, D);  line(W - t, t, W - t, D - t)  # شرقي

    # --- جدار داخلي عند x=6 بسماكة 15 سم مع باب 3.0→3.9
    xi = 6.0
    line(xi, t, xi, 3.0);      line(xi + ti, t, xi + ti, 3.0)
    line(xi, 3.9, xi, D - t);  line(xi + ti, 3.9, xi + ti, D - t)
    line(xi, 3.0, xi + ti, 3.0);  line(xi, 3.9, xi + ti, 3.9)
    door_swing(xi + ti, 3.0, 0, 1, 1, 0, 0.9)    # يفتح نحو الغرفة الشرقية
    sh.finish(color=(0, 0, 0), width=0.5)

    # خط أبعاد (يجب ألا يُكتشف كجدار)
    sh.draw_line(P(0, -0.8), P(W, -0.8))
    sh.finish(color=(0.4, 0.4, 0.4), width=0.2)
    sh.commit()

    out = Path(__file__).parent / "sample_plan.pdf"
    doc.save(out)
    print("تم إنشاء:", out)


if __name__ == "__main__":
    main()

__pycache__/
*.pyc
venv/
.venv/
output/*
!output/.gitkeep
.DS_Store
.streamlit/secrets.toml

"""
ahmednah — من مخطط PDF إلى نموذج Revit
واجهة Streamlit: رفع مخطط PDF ← الجدران والأبواب والشبابيك ← حزمة Revit (Excel + Dynamo)

التشغيل محلياً:
    streamlit run app.py
"""

import io
from pathlib import Path

import pymupdf
import streamlit as st
from PIL import Image, ImageDraw

from core.excel_exporter import export_to_excel, lines_dataframe, openings_dataframe, walls_dataframe
from core.package import build_revit_package
from core.pdf_extractor import render_page_png
from core.pipeline import run

SAMPLE = Path(__file__).parent / "samples" / "sample_plan.pdf"
NUM_COLS = {c: st.column_config.NumberColumn(c, format="%.2f")
            for c in ["X1", "Y1", "X2", "Y2", "X", "Y", "الطول (م)", "السماكة (م)", "العرض (م)",
                      "سماكة الجدار"]}
MAX_RENDER_PX = 3000  # حد لحجم صورة المعاينة حتى لا تمتلئ ذاكرة السيرفر مع لوحات A0

st.set_page_config(page_title="ahmednah · PDF ← Revit", page_icon="🏗️", layout="wide")

# اتجاه عربي (من اليمين لليسار) للنصوص، مع إبقاء الجداول والأرقام كما هي
st.markdown("""
<style>
  .stMainBlockContainer, section[data-testid="stSidebar"] { direction: rtl; text-align: right; }
  [data-testid="stDataFrame"], [data-testid="stImage"] { direction: ltr; }
  .ahm-sub { color: #6b7280; margin-top: -0.8rem; }
</style>
""", unsafe_allow_html=True)


# ---------------- المعالجة (مع تخزين مؤقت: لا نعيد الحساب عند كل نقرة) ----------------
@st.cache_data(show_spinner=False, max_entries=8)
def process(pdf_bytes, page_no, scale, min_thk, max_thk, angle_tol, min_overlap, min_line,
            do_join, do_norm, do_open):
    return run(pdf_bytes, page_number=page_no, scale=scale, min_thk=min_thk, max_thk=max_thk,
               angle_tol=angle_tol, min_overlap=min_overlap, min_line_length=min_line,
               join=do_join, normalize=do_norm, openings=do_open)


@st.cache_data(show_spinner=False, max_entries=8)
def page_image(pdf_bytes, page_no, zoom):
    return render_page_png(pdf_bytes, page_no, zoom)


@st.cache_data(show_spinner=False, max_entries=8)
def page_count(pdf_bytes):
    return pymupdf.open(stream=pdf_bytes, filetype="pdf").page_count


# ---------------- الرأس ----------------
st.title("🏗️ ahmednah")
st.markdown('<p class="ahm-sub">ارفع مخططاً أرضياً PDF مصدَّراً من AutoCAD، '
            'واحصل على الجدران والأبواب والشبابيك جاهزة لـ Revit</p>', unsafe_allow_html=True)

# ---------------- الإعدادات ----------------
with st.sidebar:
    st.header("⚙️ الإعدادات")
    scale = st.number_input("مقياس الرسم 1:", min_value=1, value=100, step=10,
                            help="المقياس الذي صُدِّر به المخطط من AutoCAD (مثلاً 1:100 أو 1:50)")
    c1, c2 = st.columns(2)
    min_thk = c1.number_input("أقل سماكة (سم)", value=10.0, step=1.0) / 100
    max_thk = c2.number_input("أكبر سماكة (سم)", value=30.0, step=1.0) / 100
    with st.expander("إعدادات متقدمة"):
        angle_tol = st.slider("سماحية التوازي (درجة)", 0.5, 5.0, 2.0, 0.5)
        min_overlap = st.number_input("أقل طول جدار (م)", value=0.20, step=0.05)
        min_line = st.number_input("تجاهل الخطوط الأقصر من (م)", value=0.20, step=0.05)
        do_join = st.checkbox("وصل زوايا الجدران", value=True)
        do_norm = st.checkbox("نقل الأصل (0,0) إلى زاوية المبنى", value=True)
        do_open = st.checkbox("اكتشاف الأبواب والشبابيك", value=True)
    st.divider()
    with st.expander("ℹ️ كيف أستخدم النتيجة في Revit؟"):
        st.markdown("""
1. حمّل **حزمة Revit** وفك ضغطها.
2. في Revit: **Manage ← Dynamo ← Open ← ahmednah.dyn**
3. في عقدة **1. Excel File** اختر ملف Excel من الحزمة.
4. اضغط **Run**.
""")
    st.caption("🔒 الملفات تُعالج في الذاكرة فقط ولا تُحفظ على السيرفر.")

# ---------------- الرفع ----------------
up_col, sample_col = st.columns([4, 1], vertical_alignment="bottom")
uploaded = up_col.file_uploader("ارفع ملف PDF للمخطط الأرضي", type=["pdf"])
if sample_col.button("🧪 جرّب مخططاً تجريبياً", width="stretch"):
    st.session_state.use_sample = True

if uploaded:
    st.session_state.use_sample = False
    pdf_bytes, file_name = uploaded.getvalue(), uploaded.name
elif st.session_state.get("use_sample"):
    pdf_bytes, file_name = SAMPLE.read_bytes(), "sample_plan.pdf"
    st.info("تعرض الآن المخطط التجريبي (مقياس 1:100). ارفع ملفك في أي وقت.")
else:
    st.markdown("""
#### كيف يعمل؟
1. **ارفع** مخططاً أرضياً PDF، صدّره من AutoCAD مباشرة (وليس ممسوحاً ضوئياً).
2. **اضبط المقياس** من القائمة الجانبية ليطابق مقياس التصدير.
3. **راجع** الجدران والأبواب والشبابيك المكتشفة فوق المخطط.
4. **حمّل حزمة Revit** وشغّلها في Dynamo.
""")
    st.stop()

base_name = Path(file_name).stem

try:
    n_pages = page_count(pdf_bytes)
except Exception:
    st.error("تعذّرت قراءة الملف. تأكد أنه PDF سليم وغير محمي بكلمة مرور.")
    st.stop()

page_no = st.selectbox("الصفحة", range(1, n_pages + 1)) - 1 if n_pages > 1 else 0

with st.spinner("جارٍ تحليل المخطط..."):
    try:
        lines, walls, ops, info, offset, meta = process(
            pdf_bytes, page_no, scale, min_thk, max_thk, angle_tol, min_overlap, min_line,
            do_join, do_norm, do_open)
    except Exception as e:
        st.error(f"حدث خطأ أثناء التحليل: {e}")
        st.stop()

k = info["factor_m_per_pt"]
page_w_pt, page_h_pt = info["page_width_m"] / k, info["page_height_m"] / k
zoom = min(2.0, MAX_RENDER_PX / max(page_w_pt, page_h_pt))

if not lines:
    st.warning("لم أجد أي خطوط متجهية في هذه الصفحة. "
               "على الأغلب الملف ممسوح ضوئياً (صورة) وليس مصدَّراً من AutoCAD مباشرة.")
    st.image(page_image(pdf_bytes, page_no, zoom))
    st.stop()

if not walls:
    st.warning("وجدت خطوطاً لكن بدون جدران. على الأغلب **المقياس غير صحيح** — "
               "جرّب 1:50 أو 1:100 أو 1:200 من القائمة الجانبية.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("الخطوط", len(lines))
m2.metric("الجدران", len(walls))
m3.metric("الأبواب", sum(o.kind == "Door" for o in ops))
m4.metric("الشبابيك", sum(o.kind == "Window" for o in ops))

# ---------------- العرض ----------------
left, right = st.columns([5, 4])

with left:
    show_overlay = st.toggle("إظهار العناصر المكتشفة فوق المخطط", value=True)
    img = Image.open(io.BytesIO(page_image(pdf_bytes, page_no, zoom))).convert("RGB")
    if show_overlay and walls:
        draw = ImageDraw.Draw(img)
        ox, oy = offset  # الجدران مزاحة؛ نعيدها لمكانها على الورقة للرسم

        def to_px(x, y):
            return ((x + ox) / k * zoom, (page_h_pt - (y + oy) / k) * zoom)

        for w in walls:
            draw.line([to_px(w.x1, w.y1), to_px(w.x2, w.y2)], fill=(230, 60, 40),
                      width=max(2, int(w.thickness / k * zoom * 0.6)))
            cx, cy = to_px((w.x1 + w.x2) / 2, (w.y1 + w.y2) / 2)
            draw.text((cx + 3, cy + 3), str(w.wall_id), fill=(20, 60, 200))

        colors = {"Door": (30, 90, 220), "Window": (20, 170, 90), "Opening": (240, 160, 0)}
        by_id = {w.wall_id: w for w in walls}
        for o in ops:
            h = by_id[o.host_wall_id]
            L = max(h.length, 1e-6)
            ux, uy = (h.x2 - h.x1) / L, (h.y2 - h.y1) / L
            a = to_px(o.x - ux * o.width / 2, o.y - uy * o.width / 2)
            b = to_px(o.x + ux * o.width / 2, o.y + uy * o.width / 2)
            draw.line([a, b], fill=colors[o.kind], width=max(4, int(o.wall_thickness / k * zoom * 1.3)))
            cx, cy = to_px(o.x, o.y)
            draw.text((cx + 6, cy - 14), f"{o.kind[0]}{o.opening_id}", fill=colors[o.kind])
    # قصّ الصورة على حدود الرسم (المخطط غالباً لا يملأ الورقة)
    xs = [v / k * zoom for l in lines for v in (l.x1, l.x2)]
    ys = [(page_h_pt - v / k) * zoom for l in lines for v in (l.y1, l.y2)]
    pad = 0.04 * max(max(xs) - min(xs), max(ys) - min(ys)) + 10
    img = img.crop((max(0, int(min(xs) - pad)), max(0, int(min(ys) - pad)),
                    min(img.width, int(max(xs) + pad)), min(img.height, int(max(ys) + pad))))
    st.image(img, width="stretch")
    st.caption("🔴 جدار   🔵 باب   🟢 شباك   🟠 فتحة بدون باب")

with right:
    excel_bytes = export_to_excel(walls, lines, meta=meta, openings=ops)
    st.download_button("📦 تحميل حزمة Revit (Excel + Dynamo)", type="primary",
                       data=build_revit_package(excel_bytes, base_name),
                       file_name=f"{base_name}_ahmednah.zip", mime="application/zip",
                       width="stretch", disabled=not walls)
    st.download_button("⬇️ ملف Excel فقط", data=excel_bytes,
                       file_name=f"{base_name}_walls.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="stretch")

    tab_w, tab_o = st.tabs([f"الجدران ({len(walls)})", f"الفتحات ({len(ops)})"])
    with tab_w:
        st.dataframe(walls_dataframe(walls).rename(columns={
            "Wall_ID": "رقم", "Length_m": "الطول (م)", "Thickness_m": "السماكة (م)"}),
            width="stretch", hide_index=True, height=360, column_config=NUM_COLS)
    with tab_o:
        st.dataframe(openings_dataframe(ops).rename(columns={
            "Opening_ID": "رقم", "Type": "النوع", "Host_Wall_ID": "الجدار",
            "Width_m": "العرض (م)", "Swing_Side": "جهة الفتح", "Hinge_At": "المفصلة",
            "Wall_Thickness_m": "سماكة الجدار"}),
            width="stretch", hide_index=True, height=360, column_config=NUM_COLS)

with st.expander(f"الخطوط الخام ({len(lines)})"):
    st.dataframe(lines_dataframe(lines), width="stretch", hide_index=True)

"""
تشغيل الاستخراج من سطر الأوامر بدون واجهة (مفيد للتجربة السريعة).

مثال:
    python extract_cli.py samples/sample_plan.pdf --scale 100
النتيجة تُحفظ في: output/<اسم الملف>_walls.xlsx
"""

import argparse
from pathlib import Path

from core.pipeline import run
from core.excel_exporter import export_to_excel


def main():
    p = argparse.ArgumentParser(description="ahmednah - استخراج الجدران من PDF")
    p.add_argument("pdf")
    p.add_argument("--scale", type=float, default=100, help="مقياس الرسم (100 يعني 1:100)")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--min", type=float, default=10, help="أقل سماكة جدار بالسم")
    p.add_argument("--max", type=float, default=30, help="أكبر سماكة جدار بالسم")
    p.add_argument("--no-join", action="store_true", help="بدون وصل الزوايا")
    p.add_argument("--keep-origin", action="store_true", help="إبقاء أصل الورقة")
    a = p.parse_args()

    lines, walls, ops, info, offset, meta = run(
        a.pdf, page_number=a.page - 1, scale=a.scale, min_thk=a.min / 100, max_thk=a.max / 100,
        join=not a.no_join, normalize=not a.keep_origin)

    out = Path("output") / (Path(a.pdf).stem + "_walls.xlsx")
    out.parent.mkdir(exist_ok=True)
    export_to_excel(walls, lines, str(out), meta=meta, openings=ops)

    print(f"الخطوط: {len(lines)} | الجدران: {len(walls)}")
    for w in walls:
        print(f"  #{w.wall_id:>3}  ({w.x1:7.2f},{w.y1:7.2f}) → ({w.x2:7.2f},{w.y2:7.2f})"
              f"  L={w.length:6.2f}م  t={w.thickness*100:5.1f}سم")
    print(f"الفتحات: {len(ops)}")
    for o in ops:
        extra = f"  فتح={o.swing_side:+d} مفصلة={o.hinge_at}" if o.kind == "Door" else ""
        print(f"  #{o.opening_id:>3}  {o.kind:<8} جدار {o.host_wall_id}  ({o.x:6.2f},{o.y:6.2f})"
              f"  عرض={o.width:.2f}م{extra}")
    print(f"تم الحفظ: {out}")


if __name__ == "__main__":
    main()

# ahmednah — من مخطط PDF إلى نموذج Revit

تحويل مخطط أرضي PDF (مصدَّر من AutoCAD) إلى جدول جدران جاهز لـ Revit.

## التشغيل
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
python samples/make_sample.py      # مخطط تجريبي (اختياري)
streamlit run app.py               # الواجهة على http://localhost:8501
```

من سطر الأوامر بدون واجهة:
```bash
python extract_cli.py samples/sample_plan.pdf --scale 100
```

## الهيكل
```
ahmednah/
├── app.py                 واجهة Streamlit
├── extract_cli.py         تشغيل من سطر الأوامر
├── requirements.txt
├── core/
│   ├── pdf_extractor.py   قراءة PDF واستخراج الخطوط (PyMuPDF)
│   ├── wall_detector.py   تمييز الجدران من الخطوط المتوازية
│   ├── wall_joiner.py     وصل الزوايا + نقل الأصل (المرحلة 2)
│   ├── openings.py        الأبواب والشبابيك + دمج الجدران المستضيفة (المرحلة 3)
│   ├── pipeline.py        المسار الكامل في دالة واحدة
│   └── excel_exporter.py  الحفظ في Excel
├── dynamo/                (المرحلة 2)
│   ├── ahmednah_walls.dyn     ملف Dynamo جاهز
│   ├── ahmednah_walls.py      كود بايثون: قراءة الجدران
│   ├── ahmednah_openings.py   كود بايثون: الأبواب والشبابيك (المرحلة 3)
│   └── build_dyn.py           يعيد بناء .dyn بعد تعديل الكود
├── samples/make_sample.py مولّد مخطط تجريبي
└── output/                ملفات Excel الناتجة
```

## ملف Excel
- ورقة `Walls`: Wall_ID, X1, Y1, X2, Y2, Length_m, Thickness_m  (بالمتر، Y للأعلى، الإحداثيات لخط محور الجدار)
- ورقة `Lines`: كل الخطوط الخام للمراجعة
- ورقة `Openings`: Opening_ID, Type (Door/Window/Opening), Host_Wall_ID, X, Y, Width_m, Wall_Thickness_m, Swing_Side, Hinge_At, Leaves
- ورقة `Info`: المقياس وإزاحة الأصل

## المرحلة 2: Revit
1. افتح مشروع Revit (أو قالباً جديداً) ← Manage ← Dynamo.
2. افتح `dynamo/ahmednah_walls.dyn`.
3. في عقدة "1. Excel File" اختر ملف Excel الناتج.
4. اضغط Run. تظهر الجدران بارتفاع 3.5 م، ويظهر تقرير في عقدة Report.

## المرحلة 3: الأبواب والشبابيك
نفس ملف `ahmednah_walls.dyn` — العقدة الثانية تضع الأبواب والشبابيك بعد الجدران تلقائياً.
- المدخلات 4 و5 اختيارية: اسم عائلة/نوع الباب والشباك (فارغ = أول عائلة محمّلة).
- إذا فتحت كل الأبواب للجهة الخطأ: غيّر `SWING_TOWARD_FACING` في أعلى كود العقدة.
- إذا كانت كل المفصلات في الطرف الخطأ: غيّر `HINGE_TOWARD_HAND`.

## المرحلة 4: النشر أونلاين (Streamlit Community Cloud — مجاني)
1. أنشئ مستودعاً جديداً على GitHub باسم `ahmednah` (Public).
2. من داخل مجلد المشروع:
   ```bash
   git remote add origin https://github.com/<اسم-حسابك>/ahmednah.git
   git branch -M main
   git push -u origin main
   ```
3. ادخل https://share.streamlit.io وسجّل الدخول بحساب GitHub.
4. Create app ← اختر المستودع `ahmednah`، الفرع `main`، والملف `app.py`.
5. (اختياري) اختر رابطاً مثل `ahmednah.streamlit.app` ← Deploy.

أي تعديل تدفعه بعدها إلى GitHub (`git push`) يُحدِّث التطبيق تلقائياً.

pymupdf>=1.24
streamlit>=1.50
pandas>=2.0
openpyxl>=3.1
pillow>=10.0
