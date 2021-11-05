####################
 Installation Guide
####################

System Prerequisites
####################

PCVS requires **python3.5+** before being installed. We encourage users to use
virtual environment before installing PCVS, especially if targeting a
single-user usage. To create a virtual environment, create & actiate it
**before** using pip3. Please check `venv
<https://docs.python.org/3/library/venv.html>`_ (native), `virtualenv
<https://virtualenv.pypa.io/en/stable/>`_ (external package) or even `pyenv
<https://github.com/pyenv/pyenv>`_ (third-party tool) to manage them.

Here some quickstarts for each approach:

.. code-block:: bash

    $ python3 -m venv ./env/
    # to use it:
    $ source env/bin/activate
    # Work in virtual environment
    $ deactivate

.. code-block:: bash

    # install first:
    $ pip3 install virtualenv
    $ virtualenv ./env/
    # to use it:
    $ source ./env/bin/activate
    # work...
    $ deactivate

.. code-block:: bash

    # install first:
    $ curl https://pyenv.run | bash
    $ pyenv virtualenv my_project
    # to use it:
    $ pyenv activate my_project
    # work...
    $ pyenv deactivate

Installation from PyPI
######################

The simplest way to install PCVS is through **PyPI** repositories. It will fetch
the lastest release but a specific version can be specified:

.. code-block:: bash

	$ pip3 install pcvs
	# OR
	$ pip3 install pcvs<=0.5.0


Installation from sources
#########################

The source code is also available on Github, based on Setuptools, the manual
installation is pretty simple. The latest release (and any previous archive) is
also available on the `website <https://pcvs.io/download>`_. To checkout the
latest release:

.. code-block:: bash

	$ git clone https://github.com/cea-hpc/pcvs.git pcvs_latest
	$ pip3 install ./pcvs_latest
	# OR
	$ python3 ./pcvs_latest/setup.py install

Managing Dependencies
#####################

Installing only dependencies come in two way: ``requirements.txt`` gathers
production-side deps, required for PCVS to work, while
``requirements-dev.txt`` contains (in addition to the base) the validation
toolkit (pytest, coverage, etc.):

.. code-block:: bash

    $ pip3 install -r requirements.txt
    $ pip3 install -r requirements-dev.txt
    # allowing to use:
    $ coverage run

Dealing with offline networks
=============================

In some scenarios, it may not be possible to access PyPI mirrors to download
dependencies (or even PCVS itself). Procedures below will describe how
to download dep archives locally on a machine with internet access and then make them
available for installation once manually moved to the 'offline' network. It
consists in two steps. First, download the deps and create and archive
(considering the project is already cloned locally):

.. code-block:: bash

    $ git clone https://github.com/cea-hpc/pcvs.git # if not already done
	$ pip3 download . -d ./pcvs_deps
	# OR, select a proper requirements file
	$ pip3 download -r requirements-dev.txt -d ./pcvs_deps
	$ tar czf pcvs_deps.tar.gz ./pcvs_deps

Once the archive moved to the offline network (=where one wants to install
PCVS), we are still considering PCVS is cloned locally:

.. code-block:: bash

	$ tar xf ./pcvs_deps.tar.gz
	$ pip3 install . --find-links ./pcvs_deps --no-index
	# or any installation variations (-e ...)

.. warning::
    Please use extra caution when using this method with different architectures
    between source & destination. By default, pip will download
    source-compatible wheel/source package, which may not be suited for the
    target machine.

pip provides options to select a given platform/target python version, which
differ from the current one. Note in that case no intermediate source package will be used, only
distributed versions (compiled one). To 'accept' it, you must specify
``--only-binary=:all:`` to force downloading distrution packages (but will
failed if not provided) or ``--no-deps`` to exclude any dependencies to be
downloade (and should be taken care manually):

.. code-block:: bash

    $ pip3 download -r ... -d ... --platform x86_64 --python-version 3.5.4 [--only-binary=:all:|--no-deps]


Important note
==============

* PCVS requires Click >= 8.0, latest versions changed a critical keyword (to
  support completion) not backward compatible. Furthermore, Flask also have a
  dep to Click>7.1. 
* To manage dict-based configuration object, PCVS relies on `Addict
  <https://github.com/mewwts/addict>`_. Not common, planned to be replaced but
  still required to ease configuration management process through PCVS. 
* Banks are managed through Git repositories. Thus, PCVS relies on `pygit2
  <https://www.pygit2.org/>`_. One major issue is when pygit2 deployement requires
  to be rebuilt, as a strong dep to libgit2 development headers is required and
  may not be always provided. As a workaround for now:

  * Install a more recent pip version, able to work with wheel package
    (>20.x). This way, the pygit2 package won't have to be reinstalled.
  * install libgit2 headers manually

.. note::
    A quick fix to install pygit2/libgit2 is to rely on `Spack
    <https://spack.io/>`_. Both are available for installation: ``libgit2`` &
    ``py-pygit2``. Be sure to take a proper version above **1.x**.