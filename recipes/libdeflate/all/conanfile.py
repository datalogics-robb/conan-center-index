from conan import ConanFile
from conan.tools.microsoft import is_msvc, VCVars, unix_path
from conan.tools.files import export_conandata_patches, apply_conandata_patches, get, chdir, rmdir, copy, rm
from conan.tools.env import VirtualBuildEnv
from conan.tools.layout import basic_layout
from conan.tools.gnu import Autotools, AutotoolsToolchain
import os

required_conan_version = ">=1.52.0"


class LibdeflateConan(ConanFile):
    name = "libdeflate"
    description = "Heavily optimized library for DEFLATE/zlib/gzip compression and decompression."
    license = "MIT"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/ebiggers/libdeflate"
    topics = ("libdeflate", "compression", "decompression", "deflate", "zlib", "gzip")
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
    }

    @property
    def _is_clangcl(self):
        return self.settings.compiler == "clang" and self.settings.os == "Windows"

    @property
    def _settings_build(self):
        return getattr(self, "settings_build", self.settings)

    def export_sources(self):
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            try:
                del self.options.fPIC
            except Exception:
                pass
        try:
            del self.settings.compiler.libcxx
        except Exception:
            pass
        try:
            del self.settings.compiler.cppstd
        except Exception:
            pass

    def layout(self):
        basic_layout(self, src_folder="src")

    def build_requirements(self):
        if self._settings_build.os == "Windows" and not is_msvc(self):
            self.win_bash = True
            if not self.conf.get("tools.microsoft.bash:path", default=False, check_type=str):
                self.tool_requires("msys2/cci.latest")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], destination=self.source_folder, strip_root=True)

    def generate(self):
        env = VirtualBuildEnv(self)
        env.generate()

        if is_msvc(self) or self._is_clangcl:
            vc = VCVars(self)
            vc.generate()
        else:
            tc = AutotoolsToolchain(self)
            tc.generate()

    def _build_nmake(self):
        with chdir(self, self.source_folder):
            target = "libdeflate.dll" if self.options.shared else "libdeflatestatic.lib"
            self.run(f"nmake /f Makefile.msc {target}")

    def _build_make(self):
        autotools = Autotools(self)
        with chdir(self, self.source_folder):
            autotools.make()

    def build(self):
        apply_conandata_patches(self)
        if is_msvc(self) or self._is_clangcl:
            self._build_nmake()
        else:
            self._build_make()

    def _package_windows(self):
        copy(self, "libdeflate.h", dst=os.path.join(self.package_folder, "include"), src=self.source_folder)
        if self.options.shared:
            copy(self, "*deflate.lib", dst=os.path.join(self.package_folder, "lib"), src=self.source_folder)
            copy(self, "*deflate.dll", dst=os.path.join(self.package_folder, "bin"), src=self.source_folder)
        else:
            copy(self, "*deflatestatic.lib", dst=os.path.join(self.package_folder, "lib"), src=self.source_folder)

    def _package_make(self):
        autotools = Autotools(self)
        with chdir(self, self.source_folder):
            # Note: not actually an autotools project, is a Makefile project.
            autotools.install(args=[f"PREFIX={unix_path(self, self.package_folder)}"])
        rmdir(self, os.path.join(self.package_folder, "bin"))
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rm(self, "*.a" if self.options.shared else "*.[so|dylib]*", os.path.join(self.package_folder, "lib") )

    def package(self):
        copy(self, "COPYING", 
            src=os.path.join(self.source_folder, self.source_folder), 
            dst=os.path.join(self.package_folder, "licenses"
        ))
        if self.settings.os == "Windows":
            self._package_windows()
        else:
            self._package_make()

    def package_info(self):
        self.cpp_info.set_property("pkg_config_name", "libdeflate")
        prefix = "lib" if self.settings.os == "Windows" else ""
        suffix = "static" if self.settings.os == "Windows" and not self.options.shared else ""
        self.cpp_info.libs = [f"{prefix}deflate{suffix}"]
        if self.settings.os == "Windows" and self.options.shared:
            self.cpp_info.defines = ["LIBDEFLATE_DLL"]
