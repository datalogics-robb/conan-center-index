import subprocess
from typing import NamedTuple, List

import dl_conan_build_tools.config
import pytest
from dl_conan_build_tools.tasks.conan import Config

from util import recipes

_config = dl_conan_build_tools.config.get_config()


class Package(NamedTuple):
    package: str
    options: List[str]

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
def prebuilt_tool_config(request):
    config = Config.from_name(request.param)
    config.validate()
    config = config.normalize()

    config.infer_additional_configuration()

    return config


@pytest.fixture(scope='package')
def tool_recipe_folder(prebuilt_tool):
    package, version = prebuilt_tool.package.split('/')
    return recipes.versions_to_folders(package)[version]


class TestBuildTools(object):
    def test_build_tool(self, prebuilt_tool, prebuilt_tool_config, tool_recipe_folder, upload_to, force_build):
        tool_options = []
        for opt in prebuilt_tool.options:
            tool_options.append('--options:host')
            tool_options.append(opt)
        force_build_options = []
        if force_build == 'package':
            force_build_options = ['--build', prebuilt_tool.package.split('/', maxsplit=1)[0]]
        elif force_build == 'with-requirements':
            force_build_options = ['--build', 'all']
        args = ['conan', 'create', tool_recipe_folder, f'{prebuilt_tool.package}@',
                '--update'] + prebuilt_tool_config.install_options() + tool_options + force_build_options
        print(f'Creating package {prebuilt_tool.package}: {" ".join(args)}')
        subprocess.run(args, check=True)
        if upload_to:
            args = ['conan', 'upload', '-r', upload_to, f'{prebuilt_tool.package}@', '--all', '--check']
        print(f'Uploading {prebuilt_tool.package}: {" ".join(args)}')
        subprocess.run(args, check=True)
