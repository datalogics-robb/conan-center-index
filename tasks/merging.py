import contextlib
import dataclasses
import getpass
import json
import platform
import shlex
import shutil
import tempfile
import textwrap
from typing import Optional

import yaml
from invoke import Exit, Task, UnexpectedExit


class MergeHadConflicts(Exception):
    pass


@dataclasses.dataclass
class MergeUpstreamConfig:
    """Configuration for the merge-upstream task."""
    cci_url: str = 'git@github.com:conan-io/conan-center-index.git'
    cci_branch: str = 'master'
    local_host: str = 'octocat.dlogics.com'
    local_organization: str = 'kam'  # TODO: datalogics
    local_branch: str = 'develop'
    local_remote_name: str = 'merge-local-remote'
    local_fork: str = getpass.getuser()
    merge_branch_name: str = 'merge-from-conan-io'
    pr_reviewers: list[str] = dataclasses.field(default_factory=list)
    pr_assignee: Optional[str] = None
    pr_labels: list[str] = dataclasses.field(default_factory=lambda: ['from-conan-io'])

    @property
    def local_url(self) -> str:
        return f'git@{self.local_host}:{self.local_organization}/conan-center-index.git'

    @property
    def fork_url(self) -> str:
        return f'git@{self.local_host}:{self.local_fork}/conan-center-index.git'

    @classmethod
    def create_from_dlproject(cls):
        """Create a MergeUpstreamConfig with defaults updated from dlproject.yaml"""
        with open('dlproject.yaml') as dlproject_file:
            dlproject = yaml.safe_load(dlproject_file)
        config_data = dlproject.get('merge_upstream', dict())
        return dataclasses.replace(cls(), **config_data)


@Task
def merge_upstream(ctx):
    '''Merge updated recipes and other files from conan-io/conan-center-index.

    If the merge does not succeed, it will open a pull request against the destination
    repository, assigning the PR, and requesting reviewers.
    '''
    config = MergeUpstreamConfig.create_from_dlproject()
    _check_preconditions(ctx, config)
    print(f'Configuration: {config}')

    with _preserving_branch_and_commit(ctx):
        _update_remote(ctx, config)
        _update_branch(ctx, config)

        # Try to merge from CCI
        try:
            _merge_and_push(ctx, config)
        except MergeHadConflicts:
            try:
                pr_body = _form_pr_body(ctx, config)
            finally:
                ctx.run('git merge --abort')
            _create_pull_request(ctx, config, pr_body)


@contextlib.contextmanager
def _preserving_branch_and_commit(ctx):
    """Context manager to run complicated sets of Git commands, while returning
    to the original branch and placing that branch back onto the original commit."""
    result = ctx.run('git rev-parse --abbrev-ref HEAD', hide='stdout')
    branch = result.stdout.strip()
    result = ctx.run('git rev-parse HEAD', hide='stdout')
    commit = result.stdout.strip()
    try:
        yield
    finally:
        if branch == 'HEAD':
            ctx.run(f'git checkout --detach {commit}')
        else:
            ctx.run(f'git checkout --force {branch}')
            ctx.run(f'git reset --hard {commit}')


def _check_preconditions(ctx, config):
    """Check the preconditions for the merge-upstream task."""
    if platform.system() not in ['Darwin', 'Linux']:
        raise Exit('Run this task on macOS or Linux')
    # https://stackoverflow.com/a/2659808/11996393
    result = ctx.run('git diff-index --quiet HEAD --', warn=True, hide='stdout')
    if not result.ok:
        raise Exit('The local worktree has uncommitted changes')
    if not shutil.which('gh'):
        raise Exit('This task requires the GitHub CLI. See installation instructions at https://cli.github.com/')
    result = ctx.run(f'gh auth status --hostname {config.local_host}', warn=True)
    if not result.ok:
        raise Exit(f'GitHub CLI must be logged in to {config.local_host}, or a token supplied in GH_TOKEN; '
                   f'see https://cli.github.com/manual/gh_auth_login')


def _update_remote(ctx, config):
    '''Make merge-local-remote point to the repo we're going to merge into
    This also makes it work in CI, where there might not be an "upstream"'''
    result = ctx.run(f'git remote get-url {config.local_remote_name}', hide='both', warn=True, pty=False)
    if result.ok and result.stdout.strip() != '':
        ctx.run(f'git remote set-url {config.local_remote_name} {config.local_url}')
    else:
        ctx.run(f'git remote add {config.local_remote_name} {config.local_url}')
    ctx.run(f'git remote update {config.local_remote_name}')


def _branch_exists(ctx, branch):
    """Return true if the given branch exists locally"""
    result = ctx.run(f'git rev-parse --quiet --verify {branch}', warn=True, hide='stdout')
    return result.ok


def _update_branch(ctx, config):
    """Check out and update branch"""
    if _branch_exists(ctx, config.local_branch):
        ctx.run(f'git checkout {config.local_branch}')
        ctx.run(f'git reset --hard {config.local_remote_name}/{config.local_branch}')
    else:
        ctx.run(f'git checkout --track {config.local_remote_name}/{config.local_branch}')


def _merge_and_push(ctx, config):
    """Attempt to merge upstream branch and push it to the local repo."""
    merge_result = ctx.run(f'git pull --no-ff --no-edit {config.cci_url} {config.cci_branch}', warn=True)
    if merge_result.ok:
        ctx.run(f'git push {config.local_remote_name} {config.local_branch}')
    else:
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
    ''').format(local_branch=config.local_branch,
                conflict_files=conflict_files_result.stdout,
                commits_on_upstream=commits_on_upstream_result.stdout,
                commits_local=commits_local_result.stdout)

    return body


def _create_pull_request(ctx, config, pr_body):
    """Create a pull request to merge in the data from upstream."""
    # Get on a merge branch
    ctx.run(f'git fetch {config.cci_url} {config.cci_branch}')
    if _branch_exists(ctx, config.merge_branch_name):
        ctx.run(f'git checkout {config.merge_branch_name}')
        ctx.run('git reset --hard FETCH_HEAD')
    else:
        ctx.run(f'git checkout -b {config.merge_branch_name} FETCH_HEAD')

    ctx.run(f'git push --force {config.fork_url} {config.merge_branch_name}')
    with tempfile.NamedTemporaryFile(prefix='pr-body', mode='w+', encoding='utf-8') as pr_body_file:
        pr_body_file.write(pr_body)
        # Before passing the filename to gh pr create, flush it so all the data is on the disk
        pr_body_file.flush()

        existing_prs = _list_merge_pull_requests(ctx, config)
        if existing_prs:
            assert len(existing_prs) == 1
            url = existing_prs[0]['url']
            ctx.run(f'gh pr edit --repo {config.local_host}/{config.local_organization}/conan-center-index '
                    f'{url} --body-file {pr_body_file.name}')
        else:
            title = shlex.quote('Merge in changes from conan-io/master')
            labels = f' --label {",".join(config.pr_labels)}' if config.pr_labels else ''
            assignee = f' --assignee {config.pr_assignee}' if config.pr_assignee else ''
            reviewer = f' --reviewer {",".join(config.pr_reviewers)}' if config.pr_reviewers else ''
            ctx.run(f'gh pr create --repo {config.local_host}/{config.local_organization}/conan-center-index '
                    f'--base {config.local_branch} '
                    f'--title {title} --body-file {pr_body_file.name} '
                    f'--head {config.local_fork}:{config.merge_branch_name}'
                    f'{labels}{assignee}{reviewer}')


def _list_merge_pull_requests(ctx, config):
    result = ctx.run(f'gh pr list --repo {config.local_host}/{config.local_organization}/conan-center-index '
                     '--json number,url,author,headRefName,headRepositoryOwner ',
                     hide='stdout',
                     pty=False)
    out = result.stdout.strip()
    requests = json.loads(out) if out else []
    return [r for r in requests if
            r['headRefName'] == config.merge_branch_name and r['headRepositoryOwner']['login'] == config.local_fork]
