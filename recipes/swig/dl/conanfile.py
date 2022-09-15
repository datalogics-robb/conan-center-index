from conans import ConanFile, tools, AutoToolsBuildEnvironment
import contextlib
import functools
import os
import shutil

required_conan_version = ">=1.33.0"


class SwigConan(ConanFile):
    name = "swig"
    description = "SWIG is a software development tool that connects programs written in C and C++ with a variety of high-level programming languages."
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "http://www.swig.org"
    license = "GPL-3.0-or-later"
    topics = ("swig", "python", "java", "wrapper")
    exports_sources = "patches/**", "cmake/*"
    settings = "os", "arch", "compiler", "build_type", "os_build", "arch_build"

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _settings_build(self):
        return getattr(self, "settings_build", self.settings)

    def requirements(self):
        self.requires("pcre/8.45")

    def build_requirements(self):
        if self._settings_build.os == "Windows" and not tools.get_env("CONAN_BASH_PATH"):
            self.build_requires("msys2/cci.latest")
        if self.settings.compiler == "Visual Studio":
            self.build_requires("winflexbison/2.5.24")
        else:
            self.build_requires("bison/3.7.6")
        self.build_requires("automake/1.16.4")

    def package_id(self):
        del self.info.settings.compiler

    def source(self):
        source = self.conan_data['sources'][self.version]
        if 'git' in source:
            git = tools.Git(folder=self._source_subfolder)
            git.clone(**source['git'])
        else:
            tools.get(**source,
                      destination=self._source_subfolder, strip_root=True)

    @property
    def _user_info_build(self):
        # If using the experimental feature with different context for host and
        # build, the 'user_info' attributes of the 'build_requires' packages
        # will be located into the 'user_info_build' object. In other cases they
        # will be located into the 'deps_user_info' object.
        return getattr(self, "user_info_build", self.deps_user_info)

    @contextlib.contextmanager
    def _build_context(self):
        env = {}
        if self.settings.compiler != "Visual Studio":
            env["YACC"] = self._user_info_build["bison"].YACC
        if self.settings.compiler == "Visual Studio":
            with tools.vcvars(self):
                env.update({
                    "CC": "{} cl -nologo".format(tools.unix_path(self._user_info_build["automake"].compile)),
                    "CXX": "{} cl -nologo".format(tools.unix_path(self._user_info_build["automake"].compile)),
                    "AR": "{} link".format(self._user_info_build["automake"].ar_lib),
                    "LD": "link",
                })
                with tools.environment_append(env):
                    yield
        else:
            with tools.environment_append(env):
                yield

    @functools.lru_cache(1)
    def _configure_autotools(self):
        autotools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
        deps_libpaths = autotools.library_paths
        deps_libs = autotools.libs
        deps_defines = autotools.defines
        if self.settings.os == "Windows" and self.settings.compiler != "Visual Studio":
            autotools.link_flags.append("-static")

        libargs = list("-L\"{}\"".format(p) for p in deps_libpaths) + list("-l\"{}\"".format(l) for l in deps_libs)
        args = [
            "PCRE_LIBS={}".format(" ".join(libargs)),
            "PCRE_CPPFLAGS={}".format(" ".join("-D{}".format(define) for define in deps_defines)),
            "--host={}".format(self.settings.arch),
            "--with-swiglibdir={}".format(self._swiglibdir),
        ]
        if self.settings.compiler == 'gcc':
            args.append("LIBS=-ldl")

        host, build = None, None

        if self.settings.compiler == "Visual Studio":
            self.output.warn("Visual Studio compiler cannot create ccache-swig. Disabling ccache-swig.")
            args.append("--disable-ccache")
            autotools.flags.append("-FS")
            # MSVC canonical names aren't understood
            host, build = False, False

        # DL: Old versions of swig-ccache needed yodl2man to build, which isn't
        # available. We don't need ccache anyway.
        if str(self.version) < tools.Version('4.0.0'):
            self.output.warn("Old versions of SWIG need yodl2man to create ccache-swig. Disabling ccache-swig.")
            args.append("--disable-ccache")

        if self.settings.os == "Macos" and self.settings.arch == "armv8":
            # FIXME: Apple ARM should be handled by build helpers
            autotools.flags.append("-arch arm64")
            autotools.link_flags.append("-arch arm64")

        autotools.libs = []
        autotools.library_paths = []

        if self.settings.os == "Windows" and self.settings.compiler != "Visual Studio":
            autotools.libs.extend(["mingwex", "ssp"])

        autotools.configure(args=args, configure_dir=self._source_subfolder,
                            host=host, build=build)
        # DL: Old versions of SWIG deposited the swigp4.ml file in the build directory, but installed them from
        # source
        if str(self.version) < tools.Version('4.0.0'):
            shutil.copy('Lib/ocaml/swigp4.ml', os.path.join(self._source_subfolder, 'Lib/ocaml/swigp4.ml'))

        return autotools

    def _patch_sources(self):
        for patch in self.conan_data.get("patches", {}).get(self.version, []):
            tools.patch(**patch)

    def build(self):
        self._patch_sources()
        with tools.chdir(os.path.join(self._source_subfolder)):
            self.run("./autogen.sh", win_bash=tools.os_info.is_windows)
        with self._build_context():
            autotools = self._configure_autotools()
            autotools.make()

    def package(self):
        self.copy(pattern="LICENSE*", dst="licenses", src=self._source_subfolder)
        self.copy(pattern="COPYRIGHT", dst="licenses", src=self._source_subfolder)
        self.copy("*", src="cmake", dst=self._module_subfolder)
        with self._build_context():
            autotools = self._configure_autotools()
            autotools.install()

    @property
    def _swiglibdir(self):
        return os.path.join(self.package_folder, "bin", "swiglib").replace("\\", "/")

    @property
    def _module_subfolder(self):
        return os.path.join("lib", "cmake")

    @property
    def _module_file(self):
        return "conan-official-{}-targets.cmake".format(self.name)

    def package_info(self):
        self.cpp_info.includedirs=[]
        self.cpp_info.names["cmake_find_package"] = "SWIG"
        self.cpp_info.names["cmake_find_package_multi"] = "SWIG"
        self.cpp_info.builddirs = [self._module_subfolder]
        self.cpp_info.build_modules["cmake_find_package"] = \
            [os.path.join(self._module_subfolder, self._module_file)]
        self.cpp_info.build_modules["cmake_find_package_multi"] = \
            [os.path.join(self._module_subfolder, self._module_file)]

        bindir = os.path.join(self.package_folder, "bin")
        self.output.info("Appending PATH environment variable: {}".format(bindir))
        self.env_info.PATH.append(bindir)

    def package_id(self):
        del self.info.settings.compiler
        del self.info.settings.os_build
        del self.info.settings.arch_build

        # Doxygen doesn't make executable code. Any package that will run is ok to use.
        # It's ok in general to use a release version of the tool that matches the
        # build os and architecture.
        compatible_pkg = self.info.clone()
        compatible_pkg.settings.build_type = 'Release'
        compatible_pkg.settings.arch = self.settings.arch_build
        compatible_pkg.settings.os = self.settings.os_build
        self.compatible_packages.append(compatible_pkg)
