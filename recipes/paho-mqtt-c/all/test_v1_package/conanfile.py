from conans import ConanFile, CMake
from conan.tools.build import cross_building
import os

class TestPackageV1Conan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    generators = "cmake", "cmake_find_package_multi"

    def build(self):
        cmake = CMake(self)
        cmake.definitions["PAHO_MQTT_C_ASYNC"] = self.options["paho-mqtt-c"].asynchronous
        cmake.definitions["PAHO_MQTT_C_WITH_SSL"] = self.options["paho-mqtt-c"].ssl
        cmake.configure()
        cmake.build()

    def test(self):
        if not cross_building(self):
            bin_path = os.path.join("bin", "test_package")
            self.run(bin_path, run_environment=True)
