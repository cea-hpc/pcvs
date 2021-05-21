PCVS Documentation
==================

PCVS stands for Parallel Computing Validation System and acts as a effort to
help validating complex HPC architecture (compilers, runtimes, resource
managers) at scale.

This work is currently supported by the French Alternative Energies and Atomic
Energy Commission (CEA). For any question and/or remarks, please contact :

* Julien JAEGER <julien.jaeger@cea.fr>

### Contributors

* Julien ADAM <adamj@paratools.com>
* Jean-Baptiste BESNARD <jbbesnard@paratools.com>

PCVS is documented through ReStructuredText. which can be found under the
`/docs` directory.

Quick installation guide
------------------------
PCVS is a setuptools-based python3 project, it can be directly installed through
`pip`:

```sh
pip install $PCVS_SOURCES
pip install pcvs  # SOON...
pcvs
```

Once done, PCVS can be directly invoked through the shell. Simply run `pcvs` to
get a basic CLI overview. The full completion can be enabled into the current
shell through: 

```sh
# bash-based completion
eval "$(_PCVS_COMPLETE=source_bash pcvs)"
#zsh-based completion
eval "$(_PCVS_COMPLETE=source_zsh pcvs)"
```

For more informatin about CLI completion through Click, please [see
here](https://click.palletsprojects.com/en/7.x/bashcomplete/#activation-script).
You may also reach the dependencies to download them separately:

```sh
pip download -r requirement.txt -d ./deps_dir
tar -czf pcvs-req.tar.gz ./deps_dir
```

To install these deps without requiring an Internet access, please first ensure
at least the same version of Python3 is used:

```sh
tar xf pcvs-req.tar.gz
pip install $PCVS_SOURCES -f . --no-index
```

Developer mode
--------------

To ease proper development within the PCVS framework while limiting conflicts
with other Python-based software, we highly recommend using virtual environments
along with `editable` installation through pip. To do so:

1. Create a virtual environment through virtualenv or the well-known wrapper.
2. Initialize it beforehand.
3. Install PCVS as "editable", meaning the installation path will point to the
source directory. Any change made to the source base will be automatically
propagated to the installed package. Here a possible approach:

```sh
#based on pure virtualenv
python3 -m virtualenv ./build
source ./build/bin/activate
pip3 install .

#Through virtualenvwrapper
mkvirtualenv pcvs  # or workon pcvs
pip3 install .
```

Do deactivate & reactivate the environment, one may proceed as follows:

```sh
# deactivate, whatever the method
deactivate
# re-activate, virtualenv-based
source ./build/bin/activate
#re-activate, virtualenvwrapper-based
workon pcvs
```

### Testing

PCVS brings its own validation system to self-assess. You need tox and
appropriate Python versions to run (no virtualenv required, handled by tox
directly):

```sh
tox # run tests & coverage for all tests (python3.6)
tox -l # available testenvs:
	clean  # delete any previous coverage runs
	tests  # run tests
	report  # buil reports (coverage.py)
	yaml-lint  # yaml formatting
	lint-generic  # code formatting
	lint-imports  # imports
	lint-docs  # strict dosctring linting
	imports  #code proper imports
	docs   # properly formatted RST documentation
```

### Installation Troubleshooting
