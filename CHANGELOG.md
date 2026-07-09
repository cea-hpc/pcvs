# CHANGELOG

All major changes to PCVS are documented here. Additional sections will help to
track what changed from each release.

The format is based on [Keep a Changelog](https://keepachangelog.com/)
## [1.1.1] -- 2026-07-09

### Fixed

- **Bank**
  - Add support for libgit2 up to libgit2-1.9.
- **Orchestator**
  - Fix interruption handler, test are now correctly saved when pcvs is interrupted with 'Ctrl+C'.
- **Config**
  - Fix config file with '.yaml' extension is now supported in addition to '.yml'.
- **CLI**
  - Fix `pcvs report` archive detection.
  - Fix `pcvs bank list` command format.
  - Fix dry-run tests are no longer validated against validation configuration and cannot fail any more.

## [1.1.0] -- 2026-03-10

### Added

- **Config**
  - Better handling on bad configurations rejection (on edit & import)
  - Compilers variants environment variables in makefiles build.
  - Support for cmake custom build directory.
  - Default values for make -j jobs at runtime.
- **DOC**
  - More documentation for criterions, machine, groups & compilers configurations.
  - merge redundant getting started, basic use and workflow documentations into a nicer tutorial.

### Fixed

- **Config**
  - ! fixed default configuration using `plugin` node instead of `defaultplugin` node.
- **CLI**
  - pcvs-debug-*.log will only be generated on errors or with high debug level.

## [1.0.0] -- 2026-02-10

### Added

- **Report**
  - Main jobs list in report TUI can now be filtered based on their success status.
- **Config**
  - Add a '<test_name>.run.iterate.inherit' entry to test / group configuration.
    If present only criterion with the name specify in the list will be used.
  - Add a 'compilers.<name>.type' entry to compiler to defined their types.
    This can be done in place of specifying file extension.
    Currently, default types are: 'cc, cxx, fortran, cuda, hip'.

### Changed

- **Config**
  - Profiles should now be split in theirs respective configs files.
    A profile is now just a list of the different configs to use. (**Breaking change**)
  - Remove profile command, profiles are now a type of configs.(**Breaking change**)
  - Update defaults configs and defaults profiles.

- **CLI**
  - change run-filter and print-filter behavior. There are now order dependents.

### Fixed

- **Bank**
  - Fix logic error in bank initialization.
- **CLI**
  - Fix shell completion.
- **Check**
  - Fix pcvs check encoding errors.
  - Fix pcvs check missing bad configurations.
- **Session**
  - Fix log file overriding each others when multiples instances of pcvs are run in the same directory.
- **Orchestator**
  - Rework scheduler algorithm to fix bad performances issues.


## [0.8.0] -- 2025-11-3

### Added

- **CLI**
  - Add `--run-filter` to filter jobs to run based on tags
  - Add `--print-filter` to filter jobs to print output based on tags
  - Add `graph` command to output graph formatted metrics about a bank (success rate, tests duration...)
  - Add `--profile-path` to specify the profile to use as a path
- **DOC**
  - Build and deploy documentation
- **Jobs**
  - Add a one hour global timeout
- **Report**
  - Add TUI to visualize results in terminal (with `--tui` option)
- **Test descriptor**
  - Support compilers wrapper
  - Add `lang` key to specify explicitly the language of the test
  - Add separated `validation` node to build section of the test descriptors -> Build tests can validated in the same way as run tests
  - Add `local` option to test descriptors criterions -> When turned to `false`, the Criterion is applied to the wrapper instead of to the program

### Changed

- **CLI**
  - Add summary table at the end of runs even with verbosity opt in
- **DOC**
  - Disable documentation generation by default
- **Errors**
  - Change most warnings returner to the user
- **Jobs**:
  - Improve plugin integration in the orchestrator
    - Split timeout in `hard_timeout` (old behavior: job is killed) and `soft_timeout` (test is marked timeout but continue until completion)
- **Profile**
  - Change compilers definition to help with adding new compilers (**Breaking change**)
  - Add `defaultplugin` key to specify a default plugin instead of copy pasting
  - Remove mandatory base64 encoding for plugins (plugins can be written in pure python)
- **Session**
  - Avoid lock contention by using a one file per session structure

### Removed

- **Jobs**
  - Remove timeout from compilation tests
  - Remove `expect_exit` validation propagated to compilation tests

### Fixed

- **Bank**
  - Fix internal issues
- **Installation**
  - Fix race condition when creating PCVS home directory
- **Jobs**
  - Fix environment export
  - Fix analysis validation based on previous runs in the bank
  - Fix analysis validation when bank is disabled
  - Fix environment propagation for Make, AutoTools and CMake build systems
- **Profile**
  - Fix default plugin overriding user plugin
  - Add information on wrong configuration
- **Orchestrator**
  - Fix scheduler pruning by removing the maximum attempts discard
  - Fix tests being queue before their dependencies
  - Fix deadlock on last job being an ERR_DEP
  - Fix deadlock on last job with wrong resources allocation
  - Fix PCVS aborting its children processes on SIGTERM (ctrl+c)
- **Report**
  - Webview: Add 404 error
- **Scan**
  - Fix file finding

## [0.7.0] -- 2023-06-9

### Added

- **Bank**
  - Store the config with the runs information
  - Store automatically metadate after run
  - Add `--message` option to tag on an entry
- **CLI**
  - Add `--successful` option to return a non-zero value if a test fails
  - Add `remote-run` command
- **Jobs**
  - Write the generated yaml from setup files
- **Report**
  - Webview: Add configuration to main session page
- **Test descriptor**
  - Add new build macro `@COMPILER_*@`
  - Integrate env/args propagation to any build system
  - Handle the `None` special case
  - Raise exception on bad-formatted values for criterion

### Changed

- **ARCHIVE**
  - New format (**Breaking change**)
- **Check**
  - Disable auto-conversion
- **CLI**
  - Change default values for options
  - Avoid real run with `--show` for `exec` command
  - Disable `--print` if `-v` is not provided
- **Errors**
  - Make errors returned to the user more explicit
- **Orchestrator**
  - Support parallelisation of jobs
  - Propagate autokill
- **Profile**
  - Save wrongly-formatted files (instead of `rej\*` files)
- **Report**
  - Webview: Make elapsed time sortable
- **YAML**
  - New syntax for describing tests and configurations (**Breaking change**)

### Removed

- **Bank**
  - Remove per bank configuration
- **Report**
  - Webview: paging -> all tests are displayed on a single page
  - Webview: autorefresh

### Fixed

- **Bank**
  - Fix archive upload
- **Check**
  - Fix wrong setup computed path
- **CLI**
  - Fix `--print errors` verbosity to be compatible with Ruamel
- **Jobs**
  - Source custom environment in setup files
  - Fix return code propagation from setup files written in shell script
- **Orchestrator**
  - Fix signal propagation to interrupt deadlocked jobs
  - Fix job pickup selection
- **Report**
  - Rebuild view with missing information
  - Fix read access when extracting archive
- **Session**
  - Fix log redirection

## [0.6.0] -- 2022-09-16

### Added

- **CLI**
  - Add support for partial names for `exec` command
  - Add `--show` option to display direct output for `exec` command
  - Add `--print` option to manage test verbosity
- **Examples**
  - Add JUnit testings + Bot example
- **Profile**
  - Add templates for *gcc*, *icc* and *mpi-slurm*
  - Add default plugin
- **Report**
  - Webview: Add Failure-only section
  - Allow archive submission
- **Test descriptor**
  - Add `analysis` method to validate a test
  - Add `op` support for criterion constraints

### Changed

- **Bank**
  - Convert to Git API
- **Jobs**
  - Manggle names with criterion name if no subtitle provided

### Removed

- **CLI**
  - Open file with EDITOR option (`-e` or `--editor`)

### Fixed

- **Orchestator**
  - Discard tests with too many attempts (avoiding deadlocks)
- **Report**
  - Webview: Fix broken links

## [0.5.0] -- 2021-11-16

### Added

- Initial release
- Bank, config & profile support
- Complete Python3.6+ rewrite
- *NEW* Orchestrator
- *NEW* Plugin architecture
- *NEW* Webview
