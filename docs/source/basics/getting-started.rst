##################
 Getting Started
##################

System Prerequisites
####################

To use PCVS you must have :

* Python 3.5+
* PCVS requirements installed
* PCVS installed (see PCVS installation

Installation
############

PCVS is a based on Setuptools to manage its installation process. It can be
installed from sources and (soon) directly from PyPI. After downloading the
latest version from the `website <https://pcvs.io/download>`:

.. code-block:: bash

	$ tar xf pcvs-${PCVS_VERSION}.tar.gz
	$ cd pcvs/
	$ pip3 install .
	# => Only runtime dependencies
	$ pip3 install -rrequirements.txt
	$ pcvs

Dependencies & offline networks
===============================

In some scenarios, it may not be possible to access PyPI mirrors to download
dependencies. The following procedures will describe how to download deps
locally on a machine with internet access and then make them available for
installation once manually moved to the 'offline' network. It consists in two
steps. First, download the deps and create and archive (considering the project
is already cloned locally):

.. code-block:: bash

	$ pip3 download . -d ./deps_dir
	# OR, select a proper requirements file
	$ pip3 download -r requirements-dev.txt -d ./deps_dir
	$ tar czf pcvs_deps.tar.gz ./deps_dir

Once the archive moved to the offline network (=where one wants to install
PCVS), we are still considering PCVS is cloned locally:

.. code-block:: bash

	$ tar xf ./pcvs_deps.tar.gz
	$ pip3 install . --find-links ./deps_dir --no-index
	# or any installation variations (-e ...)


A word about dependencies
=========================

PCVS does not have much dependencies to be built. The CLI is build upon
Click>=7. As major user's input are managed through YAML, a proper YAML
installation (currently PyYAML>=5.1) is required along with a validation support
handled by JSON parsers (as jsonschema does).

Finally, the only non-regular dependency is `Addict
<https://github.com/mewwts/addi7ct>`_, a Python module to manage dictionaries and
specially its values using a full attribute path (i.e. ``a.b.c.d``), convenient to
manage complex configuration topologies.

.. note::
	You may desire to deploy PCVS in a Python environment. To do so, first, here
	are instructions to deploy malleable containers through `virtualenvwrapper
	<https://virtualenvwrapper.readthedocs.io>`_:

	.. code-block:: bash

		$ python3 -m virtualenv ./build
		$ source ./build/bin/activate
		# OR through virtualenvwrapper
		$ mkvirtualenv pcvs-env
		$ workon pcvs-env


