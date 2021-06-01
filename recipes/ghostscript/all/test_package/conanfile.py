from conans import ConanFile, tools
from conans.errors import ConanException
from io import StringIO
import os


class TestPackageConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"

    def build_requirements(self):
        if tools.os_info.is_windows:
            self.build_requires("msys2/20200517")

    def test(self):
        gs_bin = tools.get_env("GHOSTSCRIPT")
        if gs_bin is None or not gs_bin.startswith(self.deps_cpp_info["ghostscript"].rootpath):
            raise ConanException("GHOSTSCRIPT environment variable not set")

        if not tools.cross_building(self.settings):
            self.run("{} --version".format(gs_bin), run_environment=True)

