.. _installation-guide:

####################
 Installation Guide
####################

System Prerequisites
####################

PCVS requires **python3.5+** before being installed. We encourage users to use
virtual environment before installing PCVS, especially if targeting a
single-user usage. To create a virtual environment, create & actiate it
**before** using pip3. Please check
`venv <https://docs.python.org/3/library/venv.html>`_ (native, recommended),
`virtualenv <https://virtualenv.pypa.io/en/stable/>`_ (external package) or even
`pyenv <https://github.com/pyenv/pyenv>`_ (third-party tool) to manage them.

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

Installation from sources (recommended)
#######################################

The source code is available on GitHub. To checkout the latest release:

.. code-block:: bash

    $ git clone https://github.com/cea-hpc/pcvs.git pcvs
    $ pip3 install ./pcvs
    # OR for dev env
    $ pip3 install './pcvs[dev]'

Installation from PyPI
######################

An other way to install PCVS is through **PyPI** repositories.

.. code-block:: bash

    $ pip3 install pcvs
    # OR
    $ pip3 install pcvs<=0.8.0

Dealing with offline networks
=============================

In some scenarios, it may not be possible to access PyPI mirrors to download
dependencies (or even PCVS itself). Procedures below will describe how
to download dep archives locally on a machine with internet access and then make them
available for installation once manually moved to the 'offline' network. It
consists in two steps. First, download the deps and create and archive
(considering the project is already cloned locally):

.. code-block:: bash

    $ git clone https://github.com/cea-hpc/pcvs.git pcvs && cd pcvs # if not already done
    $ pip3 download . -d ./pcvs_deps
    # OR, for devloppent environment
    $ pip3 download '.[dev]' -d ./pcvs_deps
    $ tar czf pcvs_deps.tar.gz ./pcvs_deps

Once the archive moved to the offline network (=where one wants to install
PCVS), we are still considering PCVS is cloned locally:

.. code-block:: bash

    $ tar xf ./pcvs_deps.tar.gz
    $ pip3 install . --find-links ./pcvs_deps --no-index
    # or
    $ pip3 install '.[dev]' --find-links ./pcvs_deps --no-index

.. warning::
    Please use extra caution when using this method with different architectures
    between source & destination. By default, pip will download
    source-compatible wheel/source package, which may not be suited for the
    target machine.

pip provides options to select a given platform/target python version, which
differ from the current one.
Note in that case no intermediate source package will be used,
only distributed versions (compiled one). To 'accept' it, you must specify
``--only-binary=:all:`` to force downloading distribution packages (but will
fail if not provided) or ``--no-deps`` to exclude any dependencies to be
download (and should be taken care manually):

.. code-block:: bash

    $ pip3 download . -d ... --platform x86_64 --python-version 3.5.4 [--only-binary=:all:|--no-deps]


Important note
==============

* PCVS requires Click >= 8.0, latest versions changed a critical keyword (to
  support completion) not backward compatible. Furthermore, Flask also have a
  dep to Click>7.1.
* Banks are managed through Git repositories. Thus, PCVS relies on `pygit2
  <https://www.pygit2.org/>`_. One major issue is when pygit2 deployment requires
  to be rebuilt, as a strong dep to libgit2 development headers is required and
  may not be always provided. As a workaround for now:

  * Install a more recent pip version, able to work with wheel package
    (>20.x). This way, the pygit2 package won't have to be reinstalled.
  * install libgit2 headers manually

..
    (not an issue any more)
    * :strike:`To manage dict-based configuration object`, PCVS relies on `Addict
      <https://github.com/mewwts/addict>`_. Not common, planned to be replaced but
      still required to ease configuration management process through PCVS.

.. note::
    A quick fix to install pygit2/libgit2 is to rely on `Spack
    <https://spack.io/>`_. Both are available for installation: ``libgit2`` &
    ``py-pygit2``. Be sure to take a proper version above **1.x**.
