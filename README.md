PCVS Documentation
==================

Quick installation guide
------------------------

PCVs is documented through ReStructuredText. which can be found under the `/docs` directory. Althrough an installation guide is already present there, a quick installation
guide is shown as follows:

1. Clone the repository or download the archive on the website.
2. Create a virtual environment:

	# through virtualenv
	python3 -m virtualenv ./build
	source ./build/bin/activate
	pip3 install .
	# Through virtualenvwrapper
	mkvirtualenv pcvs  # or workon pcvs
	pip3 install .

3. **temporarily** copy a proper JCHRONOSS archive within PCVS installation (to be removed):

	# Download a JCHRONOSS release (v1.3 or v1.4)
	$ wget/curl ...
	# then, put it where PCVS is installed
	# if installed under the virtualenv
	$ cp jchronoss-$version.tar.gz ./build/lib/pythonX.Y/site-packages/pcvs/

4. Enabling completion: Based on Python Click interface to manage the CLI, partial completion is available for your shell. Please run the following, **Depending on your shell**, replace <name> with
your shell name (ex: bash, zsh,...):

	eval "$(_PCVS_COMPLETE=source_<name> pcvs)"

5. PCVS is now ready to be used!


Testing
-------

PCVS brings its own validation system to self-assess. You need tox and appropriate Python
versions to run (no virtualenv required, handled by tox directly):

	$ tox # run tests & coverage for all tests (python3.6)
	$ tox -l # available testenvs:
	clean  # delete any previous coverage runs
	tests  # run tests
	report  # buil reports (coverage.py)
	yaml-lint  # yaml formatting
	lint  # code formatting
	imports  #code proper imports
	docs   # properly formatted RST documentation

About
-----

PCVS stands for Parallel Computing Validation System and acts as a effort to help validating complex HPC architecture (compilers, runtimes, resource managers) at scale.

This work is currently supported by the French Alternative Energies and Atomic Energy Commission (CEA). For any question and/or remarks, please contact :

* Julien JAEGER <julien.jaeger@cea.fr>

### Contributors

* Julien ADAM <adamj@paratools.com>
* Jean-Baptiste BESNARD <jbbesnard@paratools.com>
