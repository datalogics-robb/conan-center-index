# Specifying automatic builds of tools

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Configurations for tools](#configurations-for-tools)
  - [Standard build profiles](#standard-build-profiles)
  - [Using specific compilers](#using-specific-compilers)
- [Specifying which tools to build](#specifying-which-tools-to-build)
  - [Using a dictionary](#using-a-dictionary)
    - [Limiting which tool configs to use](#limiting-which-tool-configs-to-use)
    - [Specifying options for building the tool](#specifying-options-for-building-the-tool)
  - [Using version ranges](#using-version-ranges)

<!-- mdformat-toc end -->

You can specify that tools will be built on the various platforms. To do this,
add two dictionary keys to each platform section in `dlproject.yaml`:

- `prebuilt_tools` specifies a list of tools to build, by Conan reference
- `prebuilt_tools_configs` specifies a list of configs to use to build the
  tools, from the `configs` key in the platform.

The `build_tools` test in pytest will build the _cartesian product_ of all the
items in these two lists, in other words, by default, it will build each tool
with each config. This product can be pared down by limiting which configs are
used for which tools, see below.

Because the tools are built with pytest, the results of building the tools will
appear in the individual build page. Detailed information is available in the
HTML results in the Build Artifacts. These HTML results contain pass/fail
information, and each entry can be expanded to show the detailed log.

See also: [Nightly tool builds](jenkins-jobs.md#nightly-tool-builds)

## Configurations for tools

In the `config` section for the platform, create a config named `ReleaseTool`.
(You may see that we have configs for `DebugTool` as well, but currently the
project only builds release versions of tools). In this section, put in a host
profile, as well as a build folder, description, and request to build missing
packages.

The host profile for a tool should be set to one of the standard build profiles
from the list in the next section.

Example:

```yaml
    macos-x86_64:
        common: &macOSCommon
            build:
                - missing
        config:
            # ...other configs...
            ReleaseTool: &macOSReleaseTool
                <<: *macOSCommon
                build_folder: build-release
                description: macOS Release
                profile_host:
                    - build-profile-macos-intel
```

Note there that a YAML reference is used to include the `macOSCommon` section
into every config on macOS; this is just a way of saving typing.

From the standpoint of a project that uses split build/host profiles, the build
profile would be used for tools, but when building the tools _directly_, the
build profile is also used as the host profile.

The configs don't specify a build profile yet because not all Conan Center
packages are able to be built with split build and host files yet.

### Standard build profiles

The following standard build profiles are in the `curated-conan-center-index`
branch of the `conan-config` repository. They should be used as the build
profiles for projects that consume Conan packages, and they should be used for
building tools in this project:

- `build-profile-aix-ppc`
- `build-profile-aix-ppc-gcc`
- `build-profile-linux-arm`
- `build-profile-linux-intel`
- `build-profile-macos-arm`
- `build-profile-macos-intel`
- `build-profile-solaris-sparc`
- `build-profile-solaris-sparc-32`
- `build-profile-windows-intel`

### Using specific compilers

If `dlproject.yaml` uses the dictionary form of a `prebuilt_tools` entry, then
the configs to use can be specified on a per-tool basis. _Each config that in
use must also be in `prebuilt_tools_configs`._

On AIX, in particular, not all the tools can be built with the same compiler. To
get around this, there are two tool profiles:

```yaml
    aix:
        common: &aixCommon
            build:
                - missing
        config:
            ReleaseTool:
                <<: *aixCommon
                build_folder: build-release-tool
                description: AIX Release
                profile_host: build-profile-aix-ppc
            ReleaseToolGCC:
                <<: *aixCommon
                build_folder: build-release-tool
                description: AIX Release Tool with GCC
                profile_host: build-profile-aix-ppc-gcc
```

...and both profiles are in the `prebuilt_tools_configs` list:

```yaml
        prebuilt_tools_configs:
            - ReleaseTool
            - ReleaseToolGCC
```

Individual tools specify which of the tool configs to use.

```yaml
        prebuilt_tools:
            - package: b2/4.9.2
              configs:
                - ReleaseToolGCC
            - package: swig/1.3.40+dl.1
              options:
                  - pcre:with_bzip2=False
              configs:
                - ReleaseTool
```

**Note:** Jenkins does not currently run the AIX builds for this project,
because work on AIX had been suspended. If work on AIX starts again, CI should
be turned back on, and the tool builds checked to ensure they work.

## Specifying which tools to build

The tools to build are specified in a list under `prebuilt_tools`. Entries in
this list can either be a string, or a dictionary. A string uses the configs in
`prebuilt_tools_configs`, and default options.

Example of using a string:

```yaml
        prebuilt_tools:
            - b2/4.9.2
```

### Using a dictionary

Using a dictionary for a `prebuilt_tools` entry allows more configuration. The
fields in the dictionary are:

- `package`: the package ref
- `options`: a list of key=value option strings that are passed to the
  `conan create` command; these should be options from the tool's Conanfile, or
  `package:key=value` may be used to specify an option for one of the
  requirements of the tool.
- `configs`: a list of configs to build for the particular tool in question. Any
  config in this list must _also_ be in `prebuilt_tools_configs`.
- `recipe_from`: A string indicating the directory from which to load the
  recipe. This can be used to override the search for the recipe directory in
  `config.yml`, to use an alternate recipe.

#### Limiting which tool configs to use

Specify a list of configs, for instance, to build `b2` with gcc:

```yaml
        prebuilt_tools:
            - package: b2/4.9.2
              configs:
                  - ReleaseToolGCC
```

#### Specifying options for building the tool

Specify a list of options, for instance to build Doxygen with search turned off:

```yaml
        prebuilt_tools:
            - package: doxygen/1.9.1
              options:
                  - doxygen:enable_search=False
```

Or, to build SWIG but telling `pcre` to not use `bzip2`:

```yaml
        prebuilt_tools:
            - package: swig/4.0.2+dl.2
              options:
                  - pcre:with_bzip2=False
```

### Using version ranges

Any tool reference can be specified with a version range. The version range will
be resolved to the _latest_ available version that satisfies the version range.

For instance, the `build_tools` profile in the `curated-conan-center-index`
branch of `conan-config` specifies the latest CMake >= 3.23.0. To ensure that
the latest CMake after 3.23 is built, this `dlproject.yaml` has entries like:

```yaml
        prebuilt_tools:
            - cmake/[>=3.23.0]
```

Although the tool builder will only build the latest version that matches the
range, previous versions are still left in the Conan repository on Artifactory.
