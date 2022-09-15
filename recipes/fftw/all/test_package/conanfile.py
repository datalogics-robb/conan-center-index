from conan import ConanFile
from conan.tools.build import cross_building
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
import os


class TestPackageConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeDeps", "VirtualRunEnv"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def layout(self):
        cmake_layout(self)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables["ENABLE_DOUBLE_PRECISION"] = self.dependencies["fftw"].options.precision == "double"
        tc.variables["ENABLE_SINGLE_PRECISION"] = self.dependencies["fftw"].options.precision == "single"
        tc.variables["ENABLE_LONG_DOUBLE_PRECISION"] = self.dependencies["fftw"].options.precision == "longdouble"
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not cross_building(self):
            bin_path = os.path.join(self.cpp.build.bindirs[0], "test_package")
            self.run(bin_path, env="conanrun")
