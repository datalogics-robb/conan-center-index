cmake_minimum_required(VERSION 3.1)
project(cmake_wrapper)

if(NOT TARGET glslang)
    add_library(glslang INTERFACE) # fake target for upstream CMakeLists (glslang required by tests only)
endif()

find_package(SPIRV-Tools REQUIRED CONFIG)

add_subdirectory(src)
