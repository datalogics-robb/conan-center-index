import contextlib
import dataclasses
import getpass
import json
import logging
import os
import platform
import shlex
import shutil
import tempfile
import textwrap
from enum import Enum, auto
from typing import Optional

import dacite
import yaml
from invoke import Exit, Task, UnexpectedExit

# Name of a status file
MERGE_UPSTREAM_STATUS = '.merge-upstream-status'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class MergeHadConflicts(Exception):
    pass


class MergeStatus(Enum):
    """The status of the attempted merge. The name of this status will be placed into the
    file .merge-upstream-status."""
    UP_TO_DATE = auto()
    """The branch was already up to date."""
    MERGED = auto()
    """The branch was merged (and pushed)."""
    PULL_REQUEST = auto()
    """A pull request was necessary."""


@dataclasses.dataclass
class ConanCenterIndexConfig:
    """Configuration for Conan Center Index"""
    url: str = 'git@github.com:conan-io/conan-center-index.git'
    """URL for the Conan Center Index"""
    branch: str = 'master'
    """Branch to fetch from"""


@dataclasses.dataclass
class UpstreamConfig:
    """Configuration describing parameters for the upstream repo. (usually Datalogics)"""
    host: str = 'octocat.dlogics.com'
    """Host for the Datalogics upstream"""
    organization: str = 'datalogics'
    """Name of the upstream organization"""
    branch: str = 'develop'
    """Name of the branch that Conan Center Index is merged to"""
    remote_name: str = 'merge-upstream-remote'
    """Name of a temporary remote to create to do the work"""

    @property
    def url(self) -> str:
        """The URL for the upstream Git repository."""
        return f'git@{self.host}:{self.organization}/conan-center-index.git'


@dataclasses.dataclass
class PullRequestConfig:
    """Configuration describing parameters for the pull request"""
    host: str = 'octocat.dlogics.com'
    """Host for the pull request"""
    fork: str = getpass.getuser()
    """The fork to create the pull request on."""
    merge_branch_name: str = 'merge-from-conan-io'
    """The name of the head branch to create"""
    reviewers: list[str] = dataclasses.field(default_factory=list)
    """A list of usernames from which to request reviews"""
    assignee: Optional[str] = None
    """A username to be the assignee"""
    labels: list[str] = dataclasses.field(default_factory=lambda: ['from-conan-io'])
    """Labels to place on the pull request"""

    @property
    def url(self) -> str:
        """Return the URL to push to for the pull request."""
        return f'git@{self.host}:{self.fork}/conan-center-index.git'


@dataclasses.dataclass
class MergeUpstreamConfig:
    """Configuration for the merge-upstream task."""
    cci: ConanCenterIndexConfig = dataclasses.field(default_factory=ConanCenterIndexConfig)
    """Configuration for Conan Center Index"""
    upstream: UpstreamConfig = dataclasses.field(default_factory=UpstreamConfig)
    """Configuration for the Datalogics upstream"""
    pull_request: PullRequestConfig = dataclasses.field(default_factory=PullRequestConfig)

    class ConfigurationError(Exception):
        """Configuration error when reading data."""

    @classmethod
    def create_from_dlproject(cls):
        """Create a MergeUpstreamConfig with defaults updated from dlproject.yaml"""
        with open('dlproject.yaml') as dlproject_file:
            dlproject = yaml.safe_load(dlproject_file)
        config_data = dlproject.get('merge_upstream', dict())
        try:
            return dacite.from_dict(data_class=MergeUpstreamConfig,
                                    data=config_data,
                                    config=dacite.Config(strict=True))
        except dacite.DaciteError as exception:
            raise cls.ConfigurationError(
                f'Error reading merge_upstream from dlproject.yaml: {exception}') from exception

    def asyaml(self):
        """Return a string containing the yaml for this dataclass,
        in canonical form."""
        # sort_keys=False to preserve the ordering that's in the dataclasses
        # dict objects preserve order since Python 3.7
        return yaml.dump(dataclasses.asdict(self), sort_keys=False, indent=4)


@Task
def merge_upstream(ctx):
    '''Merge updated recipes and other files from conan-io/conan-center-index.

    If the merge does not succeed, it will open a pull request against the destination
    repository, assigning the PR, and requesting reviewers.
    '''
    config = MergeUpstreamConfig.create_from_dlproject()
    _check_preconditions(ctx, config)
    logger.info('merge-upstream configuration:\n%s', config.asyaml())

    # if anything fails past this point, the missing status file will also abort the Jenkins run.
    _remove_status_file()
    # Nested context handlers; see https://docs.python.org/3.10/reference/compound_stmts.html#the-with-statement
    with _preserving_branch_and_commit(ctx), _merge_remote(ctx, config):
        # Try to merge from CCI
        try:
            _write_status_file(_merge_and_push(ctx, config))
        except MergeHadConflicts:
            try:
                pr_body = _form_pr_body(ctx, config)
            finally:
                ctx.run('git merge --abort')
            _create_pull_request(ctx, config, pr_body)
            _write_status_file(MergeStatus.PULL_REQUEST)


def _remove_status_file():
    try:
        os.remove(MERGE_UPSTREAM_STATUS)
    except FileNotFoundError:
        pass


def _write_status_file(merge_status):
    """Write the merge status to the status file."""
    logger.info(f'Write status {merge_status.name} to file {MERGE_UPSTREAM_STATUS}')
    with open(MERGE_UPSTREAM_STATUS, 'w') as merge_upstream_status:
        merge_upstream_status.write(merge_status.name)


@contextlib.contextmanager
def _preserving_branch_and_commit(ctx):
    """Context manager to run complicated sets of Git commands, while returning
    to the original branch and placing that branch back onto the original commit."""
    logger.info('Save current checkout state...')
    result = ctx.run('git rev-parse --abbrev-ref HEAD', hide='stdout')
    branch = result.stdout.strip()
    result = ctx.run('git rev-parse HEAD', hide='stdout')
    commit = result.stdout.strip()
    try:
        yield
    finally:
        logger.info('Restore checkout state...')
        if branch == 'HEAD':
            ctx.run(f'git checkout --quiet --detach {commit}')
            ctx.run('git reset --hard HEAD')
        else:
            ctx.run(f'git checkout --quiet --force {branch}')
            ctx.run(f'git reset --hard {commit}')


def _check_preconditions(ctx, config):
    """Check the preconditions for the merge-upstream task."""
    logger.info('Check preconditions...')
    if platform.system() not in ['Darwin', 'Linux']:
        raise Exit('Run this task on macOS or Linux')
    # https://stackoverflow.com/a/2659808/11996393
    result = ctx.run('git diff-index --quiet HEAD --', warn=True, hide='stdout')
    if not result.ok:
        raise Exit('The local worktree has uncommitted changes')
    if not shutil.which('gh'):
        raise Exit('This task requires the GitHub CLI. See installation instructions at https://cli.github.com/')
    result = ctx.run(f'gh auth status --hostname {config.upstream.host}', warn=True)
    if not result.ok:
        raise Exit(f'GitHub CLI must be logged in to {config.upstream.host}, or a token supplied in GH_TOKEN; '
                   f'see https://cli.github.com/manual/gh_auth_login')


@contextlib.contextmanager
def _merge_remote(ctx, config):
    '''Make merge-local-remote point to the repo we're going to merge into
    This also makes it work in CI, where there might not be an "upstream".

    Used as a context manager, cleans up the remote when done.'''
    try:
        logger.info('Create remote to refer to destination fork...')
        result = ctx.run(f'git remote get-url {config.upstream.remote_name}', hide='both', warn=True, pty=False)
        if result.ok and result.stdout.strip() != '':
            ctx.run(f'git remote set-url {config.upstream.remote_name} {config.upstream.url}')
        else:
            ctx.run(f'git remote add {config.upstream.remote_name} {config.upstream.url}')
        ctx.run(f'git remote update {config.upstream.remote_name}')
        yield
    finally:
        logger.info('Remove remote...')
        ctx.run(f'git remote remove {config.upstream.remote_name}', warn=True, hide='both')


def _branch_exists(ctx, branch):
    """Return true if the given branch exists locally"""
    logger.info(f'Check if {branch} exists...')
    result = ctx.run(f'git rev-parse --quiet --verify {branch}', warn=True, hide='stdout')
    return result.ok


def _merge_and_push(ctx, config):
    """Attempt to merge upstream branch and push it to the local repo."""
    logger.info(f'Check out local {config.upstream.branch} branch...')
    ctx.run(f'git checkout --quiet --detach {config.upstream.remote_name}/{config.upstream.branch}')
    logger.info('Merge upstream branch...')
    ctx.run(f'git fetch {config.cci.url} {config.cci.branch}')
    # --into name sets the branch name so it says "...into develop" instead of "...into HEAD"
    # Have to fetch and use FETCH_HEAD because --into-name isn't available on git pull
    merge_result = ctx.run(
        f'git merge --no-ff --no-edit --into-name {config.upstream.branch} FETCH_HEAD', warn=True)
    if merge_result.ok:
        # Check to see if a push is necessary by counting the number of revisions
        # that differ between current head and the push destination.
        count_revs_result = ctx.run(
            f'git rev-list {config.upstream.remote_name}/{config.upstream.branch}..HEAD --count',
            hide='stdout', pty=False)
        needs_push = int(count_revs_result.stdout) != 0
        if needs_push:
            logger.info('Push to local repo...')
            ctx.run(f'git push {config.upstream.remote_name} HEAD:refs/heads/{config.upstream.branch}')
            return MergeStatus.MERGED
        else:
            logger.info('Repo is already up to date')
            return MergeStatus.UP_TO_DATE
    else:
        logger.info('Check for merge conflicts...')
        # Check for merge conflicts: https://stackoverflow.com/a/27991004/11996393
        result = ctx.run('git ls-files -u', hide='stdout', warn=True, pty=False)
        if result.ok and result.stdout.strip():
            raise MergeHadConflicts
        # Something else went wrong with the merge
        raise UnexpectedExit(merge_result)


def _form_pr_body(ctx, config):
    """Create a body for the pull request summarizing information about the merge conflicts."""
    # Note: pty=False to enforce not using a PTY; that makes sure that Git doesn't
    # see a terminal and put escapes into the output we want to format.
    logger.info('Create body of pull request message...')
    conflict_files_result = ctx.run('git diff --no-color --name-only --diff-filter=U', hide='stdout', pty=False)
    commits_on_upstream_result = ctx.run(
        'git log --no-color --merge HEAD..MERGE_HEAD --pretty=format:"%h -%d %s (%cr) <%an>"', hide='stdout', pty=False)
    commits_local_result = ctx.run(
        'git log --no-color --merge MERGE_HEAD..HEAD --pretty=format:"%h -%d %s (%cr) <%an>"', hide='stdout', pty=False)
    body = textwrap.dedent('''
        Merge changes from conan-io/conan-center-index into {local_branch}.

        This PR was automatically created due to merge conflicts in the automated merge.

        ## Conflict information

        ### List of conflict files

        {conflict_files}

        ### Commits for conflict files on `conan-io`

        {commits_on_upstream}

        ### Commits for conflict files, local

        {commits_local}
    ''').format(local_branch=config.upstream.branch,
                conflict_files=conflict_files_result.stdout,
                commits_on_upstream=commits_on_upstream_result.stdout,
                commits_local=commits_local_result.stdout)

    return body


def _create_pull_request(ctx, config, pr_body):
    """Create a pull request to merge in the data from upstream."""
    logger.info('Create pull request from upstream branch...')
    # Get the upstream ref
    ctx.run(f'git fetch {config.cci.url} {config.cci.branch}')
    # Push it to the fork the PR will be on. Have to include refs/heads in case the branch didn't
    # already exist
    ctx.run(f'git push --force {config.pull_request.url} '
            f'FETCH_HEAD:refs/heads/{config.pull_request.merge_branch_name}')
    with tempfile.NamedTemporaryFile(prefix='pr-body', mode='w+', encoding='utf-8') as pr_body_file:
        pr_body_file.write(pr_body)
        # Before passing the filename to gh pr create, flush it so all the data is on the disk
        pr_body_file.flush()

        existing_prs = _list_merge_pull_requests(ctx, config)
        if existing_prs:
            assert len(existing_prs) == 1
            url = existing_prs[0]['url']
            logger.info('Edit existing pull request...')
            ctx.run(f'gh pr edit --repo {config.upstream.host}/{config.upstream.organization}/conan-center-index '
                    f'{url} --body-file {pr_body_file.name}')
        else:
            logger.info('Create new pull request...')
            title = shlex.quote('Merge in changes from conan-io/master')
            labels = f' --label {",".join(config.pull_request.labels)}' if config.pull_request.labels else ''
            assignee = f' --assignee {config.pull_request.assignee}' if config.pull_request.assignee else ''
            reviewer = f' --reviewer {",".join(config.pull_request.reviewers)}' if config.pull_request.reviewers else ''
            ctx.run(f'gh pr create --repo {config.upstream.host}/{config.upstream.organization}/conan-center-index '
                    f'--base {config.upstream.branch} '
                    f'--title {title} --body-file {pr_body_file.name} '
                    f'--head {config.pull_request.fork}:{config.pull_request.merge_branch_name}'
                    f'{labels}{assignee}{reviewer}')


def _list_merge_pull_requests(ctx, config):
    logger.info('Check for existing pull requests...')
    result = ctx.run(f'gh pr list --repo {config.upstream.host}/{config.upstream.organization}/conan-center-index '
                     '--json number,url,author,headRefName,headRepositoryOwner ',
                     hide='stdout',
                     pty=False)
    out = result.stdout.strip()
    requests = json.loads(out) if out else []
    branch_name = config.pull_request.merge_branch_name
    fork = config.pull_request.fork
    return [r for r in requests if r['headRefName'] == branch_name and r['headRepositoryOwner']['login'] == fork]
