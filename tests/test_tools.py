import subprocess

import dl_conan_build_tools.config
import pytest
from dl_conan_build_tools.tasks.conan import Config

from util import recipes

_config = dl_conan_build_tools.config.get_config()


@pytest.fixture(scope='package',
                params=_config.get('prebuilt_tools', []))
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
    package, version = prebuilt_tool.split('/')
    return recipes.versions_to_folders(package)[version]


class TestBuildTools(object):
    def test_build_tool(self, prebuilt_tool, prebuilt_tool_config, tool_recipe_folder, upload_to):
        args = ['conan', 'create', tool_recipe_folder, f'{prebuilt_tool}@',
                '--update'] + prebuilt_tool_config.install_options()
        print(f'Creating package {prebuilt_tool}: {" ".join(args)}')
        subprocess.run(args, check=True)
        if upload_to:
            args = ['conan', 'upload', '-r', upload_to, f'{prebuilt_tool}@', '--all', '--check']
            print(f'Uploading {prebuilt_tool}: {" ".join(args)}')
            subprocess.run(args, check=True)
