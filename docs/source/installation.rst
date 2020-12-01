*************
Installation
*************
.. toctree::
	:maxdepth: 2
	
From sources
############

PCVS does not have much dependencies to be built. The CLI is build upon Click>=7.
As major user's input are managed through YAML, a proper YAML installation (currently
PyYAML>=5.1) is required along with a validation support handled by JSON parsers
(as jsonschema does).

Finally, the only non-regular dependency is `Addict <https://github.com/mewwts/addict>`_,
a convenient Python module to manage dictionaries and specially its values using a
full attribute path (i.e. `a.b.c.d`), convenient to manage complex configuration topologies.

After cloning the repository, users may want to create a virtual environment and deploy PCVS
in it:

.. code-block:: bash

	$ python3 -m virtualenv ./build
	$ source ./build/bin/activate
	# OR through virtualenvwrapper
	$ mkvirtualenv pcvs-env
	$ workon pcvs-env

One may proceed with PCVS installation inside the virtualenv:

.. code-block:: bash

	$ pip3 install .
	# or, for developement purposes
	$ pip3 install -e .
	$ pcvs --version

Temporary (dirty) hack
**********************

To effectively run jobs, PCVS is relying on a proper tool (called JCHRONOSS). This tool is 
intented to be replaced in a near future. In the meantime, the dev team chose to keep this 
dependency out of the PCVS repository (for history consistency). That's why, currently,
users must download and install JCHRONOSS sources by themselves beforehand. There is currently
two JCHRONOSS releases fully compatible with PCVS:

* **v1.3**: up-to-date version of JCHRONOSS, producing old-syntax JSON results. 
   Can be used in every situation to visualize results with the embedded 'webview' within JCHRONOSS sources
* **v1.4**: up-to-date version of JCHRONOSS, producing only the new-syntax JSON outputs. This version is
  mandatory to properly visualize results with the new visualizer provided by PCVS (and the ``pcvs report``
  command). Please note that this JCHRONOSS is not backward-compatible (from JSON aspects) with old
  result archives. It means you won't be able to visualize old result archives through ``./webview_gen_all.sh``.


Dependency management
#######################

Dep-only installation
**********************

To deal with dependencies, one may use regular ``requirements.txt`` along with pip to install them only.
For development purposes, extra dependencies are available from within ``requirements-dev.txt`` and
should be used instead of the regular one:

.. code-block:: bash

	$ pip3 install -r requirements.txt
	# OR, for dev purposes
	$ pip3 install -r requirements-dev.txt

No internet access
******************

In some scenarios, it may not possible to access pyPI mirrors to download dependencies. The following
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

