=============
Installation
=============

Build from sources
------------------

PCVS does not have much dependencies to be built. The CLI is build upon Click>=7.
As major user's input are managed through YAML, a proper YAML installation (currently
PyYAML>=5.1) is required along with a validation support handled by JSON parsers
(as jsonschema does).

Finally, the only non-regular dependency is `Addict <https://github.com/mewwts/addict>`_,
a Python module to manage dictionaries and specially its values using a
full attribute path (i.e. `a.b.c.d`), convenient to manage complex configuration topologies.

(Optional) Preparing a virtual environment
##########################################

After cloning the repository, users may want to create a virtual environment and deploy PCVS
in it:

.. code-block:: bash

	$ python3 -m virtualenv ./build
	$ source ./build/bin/activate
	# OR through virtualenvwrapper
	$ mkvirtualenv pcvs-env
	$ workon pcvs-env

Install the tool
################

From within (or not) a virtualenv, one can now proceed to the installation as follows:

.. code-block:: bash

	$ pip3 install .

For development purposes, it is possible to install extra dependencies (Pytest...), along with
an in-place version (=the installation path is hardly linked to the sources). This will
avoid developers to re-install the tool (calling ``pip install``) after any modification:

.. code-block:: bash

	$ pip3 install -e . -r requirements-dev.txt

Find the documentation
######################

PCVS is currently lacking robust documentation, so feel free to redistribute your comment
and/or partial notes to the dev team to be integrated. For what it worth, there is two different documentations that can be generated from this repo:

* the CLI is managed and documented through ``click``. The manpages can be automatically built
  with the third-party tool `click-man` (not a regular dep, should be installed manually).
  Note that these manpages may not contain more information than the content of each `--help` command.

.. code-block:: bash

	# be sure to have click-man properly installed first, not in requirements*.txt
	$ pip3 install click-man
	$ click-man --target $TARGET_MAN pcvs
	$ export MANPATH="$TARGET_MAN:$MANPATH"

* The general documentation (readthedocs.io-formatted) through `sphinx`, able to generate multiple formats:

.. code-block:: bash

	# be sure to have sphinx installed first
	$ pip3 install sphinx
	# readthedocs theme may not be included within Sphinx now:
	$ pip3 install sphinx_rtd_theme
	$ cd ./docs
	$ make  # will list available doc formats
	$ make man  # NOT the CLI man pages, but the general documentation
	$ make html  # readthedocs-based
	

Post-install: a temporary (dirty) hack
######################################

To effectively run jobs, PCVS is relying on a proper tool (called JCHRONOSS). This tool is 
intented to be replaced in a near future. In the meantime, the dev team chose to keep this 
dependency out of the PCVS repository (for history consistency). That's why, currently,
users must download and install JCHRONOSS sources by themselves beforehand. There is currently
two JCHRONOSS releases fully compatible with PCVS:

* **v1.3**: up-to-date version of JCHRONOSS, producing old-syntax JSON results. Can be used 
  in every situation to visualize results with the embedded 'webview' within JCHRONOSS sources
* **v1.4**: up-to-date version of JCHRONOSS, producing only the new-syntax JSON outputs. This version is
  mandatory to properly visualize results with the new visualizer provided by PCVS (and the ``pcvs report``
  command). Please note that this JCHRONOSS is not backward-compatible (from JSON aspects) with old
  result archives. It means you won't be able to visualize old result archives through ``./webview_gen_all.sh``.


Deal with offline networks
--------------------------

In some scenarios, it may not be possible to access PyPI mirrors to download dependencies. The following
procedures will describe how to download deps locally on a machine with internet access and then
make them available for installation once manually moved to the 'offline' network. It consists in
two steps. First, download the deps and create and archive (considering the project is already
cloned locally):

.. code-block:: bash

	$ pip3 download . -d ./deps_dir
	# OR, select a proper requirements file
	$ pip3 download -r requirements-dev.txt -d ./deps_dir
	$ tar czf pcvs_deps.tar.gz ./deps_dir

Once the archive moved to the offline network (=where one wants to install PCVS), we are still
considering PCVS is cloned locally:

.. code-block:: bash

	$ tar xf ./pcvs_deps.tar.gz
	$ pip3 install . --find-links ./deps_dir --no-index
	# or any installation variations (-e ...)

