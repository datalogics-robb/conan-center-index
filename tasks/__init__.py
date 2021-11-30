import io
import os
import yaml
from concurrent import futures
from dl_conan_build_tools.tasks import conan
from invoke import Collection, Exit
from invoke.tasks import Task, task


@task(help={'remote': 'remote to upload to, default conan-center-dl-staging',
            'package': 'name of package to upload, can be specified more than once',
            'all': 'upload all packages in recipes folder',
            'since-commit': 'upload all packages in recipes folder changed since COMMIT',
            'since-before-last-merge': 'upload all packages in recipes folder changed since just before the most '
                                       'recent merge (this is useful for automated tools)',
            'parallel': 'run uploads in parallel (default)',
            'upload': 'upload the recipe (default) (otherwise, just does the exports)'
            },
      iterable=['package'])
def upload_recipes(ctx, remote='conan-center-dl-staging', package=None, all=False, since_commit=None,
                   since_before_last_merge=False, parallel=True, upload=True):
    """Export and upload the named recipes to the given remote.

    Exports and uploads all the versions of the selected recipes to the remote."""
    packages = set()

    def update_since_commit(since_commit):
        stm = io.StringIO()
        ctx.run(f'git diff --name-only {since_commit} -- recipes', out_stream=stm, pty=False, dry=False)
        lines = stm.getvalue().strip('\n').split('\n')
        packages.update(path.split('/')[1] for path in lines if path)

    packages.update(package or [])
    if all:
        packages.update(os.listdir('recipes'))
    if since_commit:
        update_since_commit(since_commit)
    if since_before_last_merge:
        stm = io.StringIO()
        # Find most recent merge commit from current HEAD, basically the first rev that has more than one parent
        # https://stackoverflow.com/a/41464631/11996393
        ctx.run('git rev-list --min-parents=2 --max-count=1 HEAD', out_stream=stm, pty=False, dry=False)
        commit = stm.getvalue().strip('\n')
        # {commit}~1 is the first parent of {commit}; see https://git-scm.com/docs/git-rev-parse#_specifying_revisions
        update_since_commit(f'{commit}~1')

    sorted_packages = sorted(packages)
    print('*** Uploading:')
    for pkg in sorted_packages:
        print(f'    {pkg}')

    def do_upload(one_package):
        upload_one_package_name(ctx, one_package, remote, upload=upload)

    if parallel:
        upload_in_parallel(do_upload, sorted_packages)
    else:
        for one_package in sorted_packages:
            do_upload(one_package)


def upload_in_parallel(do_upload, sorted_packages, thread_name_prefix=None):
    """Upload recipes in parallel"""
    with futures.ThreadPoolExecutor(thread_name_prefix='upload_recipes') as executor:
        future_to_package = {executor.submit(do_upload, one_package): one_package for one_package in sorted_packages}
        for future in futures.as_completed(future_to_package):
            exception = future.exception()
            if exception:
                # Fail on first problem
                executor.shutdown(wait=True, cancel_futures=True)
                one_package = future_to_package[future]
                raise Exit(f'error exporting/uploading {one_package}: {exception}') from exception


def upload_one_package_name(ctx, package_name, remote, upload=True):
    """Upload one recipe to the given remote"""
    ctx.run(f'conan remove {package_name} --force')
    recipe_folder = os.path.join('recipes', package_name)
    config_yml_file = os.path.join(recipe_folder, 'config.yml')
    if os.path.exists(config_yml_file):
        with open(config_yml_file, 'r') as config_yml:
            config_data = yaml.safe_load(config_yml)
            for version, config in config_data['versions'].items():
                folder = os.path.join(recipe_folder, config['folder'])
                ctx.run(f'conan export {folder} {package_name}/{version}@')
    else:
        with os.scandir(recipe_folder) as dirs:
            for entry in dirs:
                if not entry.name.startswith('.') and entry.is_dir():
                    version = entry.name
                    folder = os.path.join(recipe_folder, version)
                    ctx.run(f'conan export {folder} {package_name}/{version}@')
    if upload:
        ctx.run(f'conan upload -r {remote} {package_name} --confirm')


tasks = []
tasks.extend([v for v in locals().values() if isinstance(v, Task)])

conan_tasks = Collection()
conan_tasks.add_task(conan.install_config)
conan_tasks.add_task(conan.login)
conan_tasks.add_task(conan.purge)

ns = Collection(*tasks)
ns.add_collection(conan_tasks, 'conan')

ns.configure({'run': {'echo': 'true'}})
