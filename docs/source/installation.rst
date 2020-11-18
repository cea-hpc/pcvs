Installation
============

From sources
-----------

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

