# conan-center-index

This is the Datalogics fork of
[conan-io/conan-center-index](https://github.com/conan-io/conan-center-index).

It contains curated branches, and Datalogics-local modifications of recipes.

It also has Invoke tasks and CI implementations that:

- Upload recipes to our own repositories on Artifactory.
- Pre-build tools with specific profiles and upload them to Artifactory.

## DL Documentation

### Configuration and daily operations

- [Using the Curated Conan Center Index Conan repositories](dl-docs/using-the-ccci-repositories.md)
  - [Building against the staging repository](dl-docs/using-the-ccci-repositories.md#building-against-the-staging-repository)
  - [Using standard build profiles](dl-docs/using-the-ccci-repositories.md#using-standard-build-profiles)
- Updating a recipe
  - Adding a new version of a package
    - In conjunction with a contribution to `conan-io/conan-center-index`
    - At DL only
  - Datalogics-only modifications to recipes
- [Specifying automatic builds of tools](dl-docs/automatic-tool-builds.md)
  - [Configurations for tools](dl-docs/automatic-tool-builds.md#configurations-for-tools)
    - [Standard build profiles](dl-docs/automatic-tool-builds.md#standard-build-profiles)
    - [Using specific compilers](dl-docs/automatic-tool-builds.md#using-specific-compilers)
  - [Specifying which tools to build](dl-docs/automatic-tool-builds.md#specifying-which-tools-to-build)
    - [Using a dictionary](dl-docs/automatic-tool-builds.md#using-a-dictionary)
      - [Limiting which tool configs to use](dl-docs/automatic-tool-builds.md#limiting-which-tool-configs-to-use)
      - [Specifying options for building the tool](dl-docs/automatic-tool-builds.md#specifying-options-for-building-the-tool)
    - [Using version ranges](dl-docs/automatic-tool-builds.md#using-version-ranges)
    - [Configurations for tools](dl-docs/automatic-tool-builds.md#configurations-for-tools)
      - [Standard build profiles](dl-docs/automatic-tool-builds.md#standard-build-profiles)
      - [Using specific compilers](dl-docs/automatic-tool-builds.md#using-specific-compilers)
  - [Using version ranges](dl-docs/automatic-tool-builds.md#using-version-ranges)
- Jenkins jobs
  - Recipe uploads
    - Forcing an upload of all recipes
  - Nightly tool builds
    - Requesting a full build
    - Building individual tools
  - Merges from `conan-io/conan-center-index` to `develop`
    - Controlling the interval of automated merges
    - Requesting a merge
  - Merging `develop` to `master` to put recipes into production

### Troubleshooting

- Analyzing build failures
- Using pytest to run the tools builders
- Resolving merge conflicts from the upstream repo
- Requesting a full build of the tools and their requirements
- Requesting a full (non-incremental) recipe upload

### Reference

- [`merge-upstream` task](dl-docs/merge-upstream.md)
  - [Automatically Resolved Merge Conflicts](dl-docs/auto-merge-conflict-resolution.md)
- [`merge-staging-to-production` task](dl-docs/merge-staging-to-production.md)
