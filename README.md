# conan-center-index

This is the Datalogics fork of
[conan-io/conan-center-index](https://github.com/conan-io/conan-center-index).

It contains curated branches, and Datalogics-local modifications of recipes.

It also has Invoke tasks and CI implementations that:

- Upload recipes to our own repositories on Artifactory.
- Pre-build tools with specific profiles and upload them to Artifactory.

## DL Documentation

### Configuration and daily operations

- Using the Curated Conan Center Index Conan repositories
  - Building against the staging repository
  - Using standard build profiles
- Updating a recipe
  - Adding a new version of a package
    - In conjunction with a contribution to `conan-io/conan-center-index`
    - At DL only
  - Datalogics-only modifications to recipes
- Specifying automatic builds of tools
  - Configurations for tools
    - Standard build profiles
    - Using specific compilers
  - Specifying which tools to build
    - Using a dictionary
      - Limiting which tool configs to use
      - Specifying options for building the tool
    - Using version ranges
- Jenkins jobs
  - Nightly tool builds
    - Requesting a full build
    - Building individual tools
  - Recipe uploads
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
