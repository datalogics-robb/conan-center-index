import dataclasses
import platform
import shutil
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
    pr_reviewers: list[str] = dataclasses.field(default_factory=list)
    pr_assignee: Optional[str] = None

    @property
    def local_url(self) -> str:
        return f'git@{self.local_host}:{self.local_organization}/conan-center-index.git'

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

    _update_remote(ctx, config)
    _update_branch(ctx, config)

    # Try to merge from CCI
    try:
        _merge_and_push(ctx, config)
    except MergeHadConflicts:
        ctx.run('git merge --abort')
        raise Exit('There were merge conflicts!')


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


def _update_branch(ctx, config):
    """Check out and update branch"""
    result = ctx.run(f'git rev-parse --quiet --verify {config.local_branch}', warn=True, hide='stdout')
    if result.ok:
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
