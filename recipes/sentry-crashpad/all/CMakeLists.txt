cmake_minimum_required(VERSION 2.8.11)
project(cmake_wrapper)

include(conanbuildinfo.cmake)
conan_basic_setup()

if(MINGW)
     find_program(JWASM_FOUND jwasm)
     if (JWASM_FOUND)
         set(CMAKE_ASM_MASM_COMPILER ${JWASM_FOUND})
         execute_process(COMMAND ${CMAKE_C_COMPILER} --version OUTPUT_VARIABLE COMPILER_VERSION_OUTPUT)
         if (COMPILER_VERSION_OUTPUT)
             if (COMPILER_VERSION_OUTPUT MATCHES "x86_64")
                 set(JWASM_FLAGS -win64)
             else()
                 set(JWASM_FLAGS -coff)
             endif()
         endif()
     endif()
endif()

add_subdirectory(source_subfolder/external/crashpad)
