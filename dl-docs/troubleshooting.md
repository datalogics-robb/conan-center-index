# Troubleshooting

Most of the time, the Curated Conan Center Index jobs run without incident.
Rarely something might fail. See the sections in this document for some
solutions to common problems.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Analyzing build failures](#analyzing-build-failures)
- [Using pytest to run the tools builders](#using-pytest-to-run-the-tools-builders)
  - [Preparation](#preparation)
  - [Finding the list of available builders](#finding-the-list-of-available-builders)
  - [Building a specific tool](#building-a-specific-tool)
- [Resolving merge conflicts from the upstream repo](#resolving-merge-conflicts-from-the-upstream-repo)

<!-- mdformat-toc end -->

## Analyzing build failures

If the nightly tools build fails, the logs may be hard to understand. Instead,
look in the artifacts for a report ending in `-build-tools.html`. It'll be named
with the name of the platform, with the architecture included if there are
different architectures.

The file is a pytest HTML report. It'll have an entry for each tool it tried to
build. The tests are named with the name of the package, its version number, the
config used to build it, and any additional options.

If you view details, the log of the build will be shown. Note that the stdout
and stderr streams are separate, so make sure to read both to find the commands
and error messages that will be run.

The first thing you should see in the output is the `conan create` command,
which might look like this:

```text
Creating package cmake/3.24.3: conan create recipes/cmake/3.x.x cmake/3.24.3@ --update --json /private/var/folders/hv/kv3kzcwd65d4swrd637s65_w0000gp/T/pytest-of-devauto/pytest-15/test_build_tool_cmake_3_24_3_R0/create.json --profile:host build-profile-macos-intel --build missing
```

Things to note that you will see in the log following that:

- The configuration of the build, showing the settings, options, configuration
  settings, and environment.
- The list of requirements and build requirements, and their packages. That may
  be useful information if the tool failed to build due to a change.

Examine the log to determine the source of the error. Fixing it may require
examining what changed in the Conan recipes or the upstream sources.

In order to view recent changes to the recipe that could have caused problems,
make sure to checkout the branch corresponding to the build (most likely
`upstream/develop`), and then use `git log` to look at patches to a single
recipe like this (assuming `cmake`):

```shell
git log --patch -- recipes/cmake
```

## Using pytest to run the tools builders

### Preparation

Make sure to run `mkenv.py` and activate the virtual environment.

Before running the tool builders, make sure that you have selected the
appropriate Conan repository. If you're working against `upstream/develop`, then
make sure to select the staging repository:

```bash
$ export DL_CONAN_CENTER_INDEX=staging
$ invoke conan.login
```

If you want to prevent conflicts with other work by using an alternate Conan
cache, you can do so by first assigning `CONAN_USER_HOME` to a different
directory, where the `.conan` directory will be created. Often the current
directory is a good choice.

```bash
$ export CONAN_USER_HOME=$PWD
$ export DL_CONAN_CENTER_INDEX=staging
$ invoke conan.login
```

### Finding the list of available builders

To find the tools that are built, use the pytest option `--collect-only` like
this:

```bash
$ pytest --collect-only
...
collected 12 items

<Package tests>
  <Module test_tools.py>
    <Class TestBuildTools>
      <Function test_build_tool[cmake/3.25.1-ReleaseTool]>
      <Function test_build_tool[cmake/3.24.3-ReleaseTool]>
      <Function test_build_tool[doxygen/1.9.1-ReleaseTool]>
      <Function test_build_tool[doxygen/1.9.2-ReleaseTool]>
      <Function test_build_tool[doxygen/1.9.1_doxygen:enable_search=False-ReleaseTool]>
      <Function test_build_tool[doxygen/1.9.2_doxygen:enable_search=False-ReleaseTool]>
      <Function test_build_tool[ninja/1.10.2-ReleaseTool]>
      <Function test_build_tool[ninja/1.11.1-ReleaseTool]>
      <Function test_build_tool[b2/4.8.0-ReleaseTool]>
      <Function test_build_tool[b2/4.9.2-ReleaseTool]>
      <Function test_build_tool[swig/1.3.40+dl.1_pcre:with_bzip2=False-ReleaseTool]>
      <Function test_build_tool[swig/4.0.2+dl.2_pcre:with_bzip2=False-ReleaseTool]>
```

### Building a specific tool

You can build a tool and see the output by using the following pytest options:

- `--capture=no` to display the output on the console instead of in the test log
- `-k` to use keywords, which can be a combination of strings and Python logical
  expressions. See the
  [doc](https://docs.pytest.org/en/7.2.x/how-to/usage.html#specifying-which-tests-to-run)
  for more information.
- `--force-build=package` will force the package to be built. Normally, Conan
  will try to download a built package and run the `test_package` against it.
- `--force-build=with-requirements` will force Conan to build not only the
  package, but all its requirements. This is an advanced option that is only
  necessary if there are deep problems with building the package.

From the usage help for pytest:

> Only run tests which match the given substring expression. An expression is a
> Python evaluatable expression where all names are substring-matched against
> test names and their parent classes. Example: `-k 'test_method or test_other'`
> matches all test functions and classes whose name contains 'test_method' or
> 'test_other', while `-k 'not test_method'` matches those that don't contain
> 'test_method' in their names. `-k 'not test_method and not test_other'` will
> eliminate the matches. Additionally keywords are matched to classes and
> functions containing extra names in their 'extra_keyword_matches' set, as well
> as functions which have names assigned directly to them. The matching is
> case-insensitive.

For instance, to build Doxygen 1.9.2 with the enable_search option:

```bash
$ pytest --capture=no -k 'doxygen and 1.9.2 and enable_search' --force-build=package
tests/test_tools.py::TestBuildTools::test_build_tool[doxygen/1.9.2_doxygen:enable_search=False-ReleaseTool] Creating package doxygen/1.9.2: conan create recipes/doxygen/all doxygen/1.9.2@ --update --json /private/var/folders/03/f8w5w_3s0xg5m1jphq243j_r0000gx/T/pytest-of-kam/pytest-1/test_build_tool_doxygen_1_9_2_0/create.json --profile:host build-profile-macos-intel --options:host doxygen:enable_search=False --build doxygen --build missing
...build...
```

If you want to build the package with `conan-create` directly, you can copy the
`conan create` command from the test output and run it. When you do this, remove
the `--json <temp-path>/create.json` option; the tests are using that to get
information about the package that was built.

```bash
$ conan create recipes/doxygen/all doxygen/1.9.2@ --update --profile:host build-profile-macos-intel --options:host doxygen:enable_search=False --build doxygen --build missing
...build...
```

**Note:** When running on Windows, remember to use double quotes for quoting
strings.

## Resolving merge conflicts from the upstream repo
