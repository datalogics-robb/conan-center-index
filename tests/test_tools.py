import json
import os
import platform
import subprocess
from typing import NamedTuple, List

import dl_conan_build_tools.config
import pytest
from dl_conan_build_tools.tasks.conan import Config

from util import recipes

_config = dl_conan_build_tools.config.get_config()


class Package(NamedTuple):
    package: str
    options: List[str] = list()
    configs: List[str] = list()

    def __str__(self):
        result = self.package
        if self.options:
            result = f'{self.package}_{"_".join(self.options)}'
        return result

    @classmethod
    def from_str_or_dict(cls, str_or_dict):
        if isinstance(str_or_dict, str):
            return cls(str_or_dict, [])
        return cls(**str_or_dict)


@pytest.fixture(scope='package',
                params=[Package.from_str_or_dict(entry) for entry in _config.get('prebuilt_tools', [])],
                ids=lambda param: str(param))
def prebuilt_tool(request):
    return request.param


@pytest.fixture(scope='package',
                params=_config.get('prebuilt_tools_configs', []))
def prebuilt_tool_config_name(request):
    return request.param


def config_from_name(config_name):
    config = Config.from_name(config_name)
    config.validate()
    config = config.normalize()

    config.infer_additional_configuration()

    return config


@pytest.fixture(scope='package')
def prebuilt_tool_config(prebuilt_tool_config_name):
    return config_from_name(prebuilt_tool_config_name)


@pytest.fixture(scope='package')
def release_tool_config():
    return config_from_name('ReleaseTool')


@pytest.fixture(scope='package')
def tool_recipe_folder(prebuilt_tool):
    package, version = prebuilt_tool.package.split('/')
    return recipes.versions_to_folders(package)[version]


@pytest.fixture(scope='package')
def msys_env(release_tool_config, tmpdir_factory):
    if platform.system() == 'Windows':
        msys2_dir = tmpdir_factory.mktemp('msys2_install')
        args = ['conan', 'install', 'msys2/cci.latest@', '-if', msys2_dir, '-g', 'json']
        args.extend(release_tool_config.install_options())
        subprocess.run(args, check=True)
        with open(msys2_dir / 'conanbuildinfo.json', 'r') as json_file:
            conanbuildinfo = json.load(json_file)
            return conanbuildinfo['deps_env_info']


@pytest.fixture(scope='package')
def msys_bin(msys_env):
    """Return the value of MSYS_BIN from the msys2 package, or None if not on Windows"""
    return (msys_env or {}).get('MSYS_BIN')


@pytest.fixture(scope='package')
def conan_env(msys_bin):
    """Create an environment with extra variables for running Conan. This may include
    setting a path to MSYS2 bash so that Conan doesn't try hooking into WSL (if installed)."""
    env = os.environ.copy()
    if msys_bin:
        env['CONAN_BASH_PATH'] = os.path.join(msys_bin, 'bash.exe')
    return env


class TestBuildTools(object):
    def test_build_tool(self, prebuilt_tool, prebuilt_tool_config_name, prebuilt_tool_config, tool_recipe_folder,
                        upload_to, force_build, tmp_path, conan_env):
        if prebuilt_tool.configs and prebuilt_tool_config_name not in prebuilt_tool.configs:
            pytest.skip(f'Skipping build because config named {prebuilt_tool_config_name} is not in the list of '
                        f'configs for this package: {", ".join(prebuilt_tool.configs)}')
        tool_options = []
        for opt in prebuilt_tool.options:
            tool_options.append('--options:host')
            tool_options.append(opt)
        force_build_options = []

        if force_build == 'package':
            force_build_options = ['--build', prebuilt_tool.package.split('/', maxsplit=1)[0],
                                   '--build', 'missing']
        elif force_build == 'with-requirements':
            force_build_options = ['--build']
        else:
            force_build_options = ['--build', 'missing']

        # Remove "missing" from the build list in the config, because it sets policy; the policy is determined by the
        # force_build_options
        config_build_without_missing = [build for build in prebuilt_tool_config.build if build != 'missing']
        config = prebuilt_tool_config._replace(build=config_build_without_missing)

        create_json = tmp_path / 'create.json'
        args = ['conan', 'create', tool_recipe_folder, f'{prebuilt_tool.package}@', '--update', '--json',
                str(create_json)] + config.install_options() + tool_options + force_build_options
        print(f'Creating package {prebuilt_tool.package}: {" ".join(args)}')
        subprocess.run(args, check=True, stderr=subprocess.STDOUT, env=conan_env)
        if upload_to:
            # upload packages mentioned in the create.json, which includes requirements used to build
            # this package, if in fact it had to be built.
            with open(create_json) as json_file:
                create_data = json.load(json_file)
            for install in create_data['installed']:
                recipe_id = install['recipe']['id']
                ref = recipe_id.split('#')[0]
                package = ref.split('/')[0]
                if package == 'msys2':
                    print(f'Not uploading {ref}, because it tends to modify itself during use.')
                    continue
                args = ['conan', 'upload', '-r', upload_to, f'{ref}@', '--all', '--check']
                print(f'Uploading {ref}: {" ".join(args)}')
                subprocess.run(args, check=True, stderr=subprocess.STDOUT, env=conan_env)
