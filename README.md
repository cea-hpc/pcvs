PCVS Documentation
==================

What's all about ? 
------------------


Installation
------------

The following walkthrouh will guide you step by step to properly install PCVS and its dependencies:
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

	# if installed under the virtualenv
	cp /archive/jchronoss-$version.tar.gz ./build/lib/pythonX.Y/site-packages/pcvs/
	# if installed in 'editable' mode (`pip install -e`)
	mkdir -p ./data/third_party/
	cp /archive/jchronoss-$version.tar.gz ./data/third_party/

4. PCVS is now ready to be used!

Enabling completion
-------------------

Based on Python Click interface to manage the CLI, partial completion is available for your shell. Please run the following, **Depending on your shell**, replace <name> with
your shell name (ex: bash, zsh,...):

	eval "$(_PCVS_COMPLETE=source_<name> pcvs)"

General documentation
---------------------

PCVS is currently lacking robust documentation, so feel free to redistribute your comment
and/or partial notes to the dev team to be integrated. For what it worth, there is two different documentations that can be generated from this repo:
* The whole CLI documentation, generated through `click-man` (on purpose, this is not a requirement for this project to be installed). But, as this documentation is based on
Click, there should not be more information displayed that printing the `--help` from the CLI directly:

	# be sure to have click-man properly installed first
	pip3 install click-man
	click-man --target $TARGET_MAN pcvs
	export MANPATH="$TARGET_MAN:$MANPATH"

* The general documentation (readthedocs.io-formatted) through `sphinx`, able to generate multiple formats:

	# be sure to have sphinx installed first
	pip3 install sphinx
	# readthedocs theme may not be included within Sphinx now:
	pip3 install sphinx_rtd_theme
	
	cd ./docs
	make  # will list available doc formats
	make man  # NOT the CLI man pages, but the general documentation
	make html  # readthedocs-based
	