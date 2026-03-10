<div align="center">
<!-- Try to fetch the image from LIHPC -->
<object
    type="image/png"
    data="https://www-lihpc.cea.fr/images/software/pcvs_logo.png"
    width=300px
>
<!-- If it fails (offline, forges...) use the file in the repo -->
<img src="docs/source/_static/pcvs_logo.png" width=300px/>
</object>
</div>

<div align="center"><h1> Parallel Computing Validation System </h1> </div>

<div align="center">

[![PyPI version](https://img.shields.io/pypi/v/pcvs)](https://pypi.org/project/pcvs/)
[![License](https://img.shields.io/pypi/l/pcvs)](https://cecill.info/licences/Licence_CeCILL-C_V1-en.html)
![Python versions](https://img.shields.io/pypi/pyversions/pcvs)
[![Docs](https://app.readthedocs.org/projects/pcvs/badge/?version=latest)](https://cea-hpc.github.io/pcvs/)

</div>

**Parallel Computing Validation System** (**PCVS**) is a Validation Orchestrator designed by and for software at scale.
Its primary target is HPC applications & runtimes but can flawlessly address smaller use cases.
PCVS can help users to create their test scenarios and reuse them among multiples implementations, a
high value when it comes to validating programming standards (like APIs & ABIs).
No matter the number of programs, benchmarks, languages, or tech non-regression bases use,
PCVS gathers in a single execution, and, with a focus on interacting with HPC batch managers efficiently,
run jobs concurrently to reduce the time-to-result overall.

## Quick installation guide

PCVS is a Python program distributed on [PyPI](https://pypi.org/project/pcvs/). It can be easily installed using `pip`.

```bash
$ pip3 install pcvs
```

Alternatively, you can install and test it from source.

<details> <summary><strong> How to install from source </strong></summary>

```bash
# Considering python3.10+
$ pip3 install .
# For dev/testing purposes, use the following to install development dependencies
$ pip3 install '.[dev]'
# Basic tests
$ tox -e pcvs-coverage
# OR
$ coverage run
```

</details>

Once installed, the program should be available as `pcvs`.

> [!TIP]
> Some PCVS specific test-suite exists,
> [PCVS-Benchmarks](https://github.com/cea-hpc/pcvs-benchmarks) is a curated set of HPC benchmarks and test suite with PCVS test descriptions

## Basic usage

> [!NOTE]
> You can add autocompletion for PCVS commands to your favorite shell
>
> ```sh
> # ZSH support
> $ eval "$(_PCVS_COMPLETE=zsh_source pcvs)"
> # BASH support
> $ eval "$(_PCVS_COMPLETE=bash_source pcvs)"
> ```

### Profiles and test description

PCVS relies on two YAML-based sets of configurations to understand the environment and the suite.

- The **profiles** describe the testing environment (compilers, machine, criterions...).
  They are split in multiple files to help compose profile from basic blocks.
  They can be manipulated through the `pcvs config` subcommand.
  For more details, you can refer to the [documentation](https://cea-hpc.github.io/pcvs/ref/config.html).

- The **test descriptions** describe the test suite (how to build, run and validate).
  They are independent from the profiles to help share suites adapted to PCVS across different platforms.
  They can be static (a plain YAML file) or dynamic (generated on the fly by a script).
  A complete example of a test description can be found in the [documentation](https://cea-hpc.github.io/pcvs/ref/examples.html).

The validity of the YAML files can be asserted using the `pcvs check` subcommand.

### Run a test suite

Once the configurations setup, they can be reused indefinitely to run tests.

```bash
$ pcvs run -p <profile> <path/to/suite>
```

Using the above command will launch PCVS on a given test suite, building and validating it.
A quick summary is available at the end of the run.

<details> <summary><strong> Commonly used options </strong></summary>

- Print per test validation
  ```bash
  $ pcvs -v run <path/to/suite>
  ```
- Print the output of the tests as well
  ```bash
  $ pcvs -v run --print [errors|all] <path/to/suite>
  ```
- Exit with a non-zero error code on test failure
  ```bash
  $ pcvs run -S <path/to/suite>
  ```
- Filter tests to run (based on tags)
  ```bash
  $ pcvs run --run-filter <list/of/tags> <path/to/suite>
  ```

</details>

### Visualize the results

Once the PCVS run completed, there are two ways to visualize the results:

- Using the webview with `pcvs report` subcommand and opening `localhost:5000` in a browser

<!-- <div align="center"><img src="./docs/source/_static/webview_example.png"></div> -->

- Using the TUI with `pcvs --tui report`

<!-- <div align="center"><img src="./docs/source/_static/tui_example.png"></div> -->

The output of the different tests can be retrieved from either as well as the complete command ran.

## Complete documentation

The user guide is hosted on GitHub pages: https://cea-hpc.github.io/pcvs.
Every CLI command has a builtin help that can be displayed using the `-h` option.
Alternatively, the documentation can be generated locally from the source code.

<details> <summary><strong> How to generate the documentation </strong></summary>

- The CLI is managed and documented through `click`.
  The manpages can be automatically built with the third-party tool `click-man` (not a dependency, should be installed manually).
  Note that these manpages may not contain more information than the content of each `--help` command.
- The general documentation use `sphinx` and can be built by running `make html` in the `docs` directory.
  The entry of the documentation will be `build/html/index.html`.

</details>

## Authors

This work is currently supported by the French Alternative Energies and Atomic
Energy Commission (CEA). For any question and/or remarks, please contact:

- Hugo TABOADA <hugo.taboada@cea.fr>
- Nicolas MARIE <nicolas.marie@uvsq.fr>

## Licensing

PCVS is distributed under the terms of the CeCILL-C Free Software Licence Agreement.

All new contributions must be made under the CeCILL-C terms.

For more details, see [COPYING](COPYING) or [CeCILL-C] website.

SPDX-Licence-Identifier: CECILL-C

<!-- Links -->

[cecill-c]: https://cecill.info/licences/Licence_CeCILL-C_V1-en.html
