.. _getting-started:

##################
 Getting Started
##################

Installation
############

The source code is available on GitHub. To checkout the latest release:
(detailed documentation in :doc:`installation`):

.. code-block:: bash

	$ git clone https://github.com/cea-hpc/pcvs.git pcvs
	$ pip3 install ./pcvs
	$ pcvs
	Usage: pcvs [OPTIONS] COMMAND [ARGS]...

	PCVS main program.
	...

Full completion (options & arguments) is provided and can be activated with:

.. code-block:: bash

	# ZSH support
	$ eval "$(_PCVS_COMPLETE=zsh_source pcvs)"
	# BASH support
	$ eval "$(_PCVS_COMPLETE=bash_source pcvs)"


PCVS-formatted test-suite
#########################

.. _test-suite-layout:

Test-suite layout
=================

While PCVS is highly customizable, it comes with templates to locally test it
without any prior knowledge. Before using PCVS, let's consider a provided
test-suite as any ``tests/`` directory
(:download:`all-reduce.c <../examples/all-reduce.c>` &
:download:`wave.c <../examples/wave.c>` provided for convenience):

.. code-block:: bash

	$ tree tests
	tests
	├── coll
	│   └── all-reduce.c
	└── pt2pt
		└── wave.c
	2 directories, 2 files


PCVS needs rules to know how to parse the test-suite above to create tests. This
will be done through ``pcvs.yml`` specification file. Such a file can be placed
anywhere in the file tree. Consider putting it directly under the ``tests/``
directory for this example. Here is the content of this file:

.. note::
	A test is the combination of a program, its arguments and the environment
	used to execute it. From PCVS' point of view, a test file does not carry the
	whole test environment. The orchestrator itself manage to build it directly
	from specification. Thus, ``pcvs.yml`` expects the user to describe programs
	to be used to build the test-suite.

.. code-block:: yaml

	# put this in test/pcvs.yml:
	all_reduce_test:
		build:
			files: ["coll/all-reduce.c"]
		run:
			program: "a.out"
	pt2pt_test:
		build:
			files: ["pt2pt/wave.c"]
		run:
			program: "a.out"

This file specifies two root nodes referred as *Test Expressions* (TE) or *Test
Descriptors* (TD). It contains subondes describing how to build programs.
A ``build`` gives information about how to build the program.
``files`` (a list *or* a string) contains the whole list of files required to
build the program (in case of a C file for instance).  With no other
information, PCVS will assume the program to be built with a compiler (no
invocation to a build system here). A ``run`` subnode instructs PCVS to execute
this program. The expected program name is ``a.out``. This is the simplest way
to integrate tests to PCVS. For a complete list of nodes to be used in a
``pcvs.yml``, please consult :ref:`te-format`

.. warning::
	Beware of tabulations, YAML indentations only supports spaces !

Execute the test-suite
######################

PCVS relies on (1) test specifications and (2) execution profile to create and
execute a full benchmarks. Building a valid profile may be complex at first but
offer a huge flexibility to solve complex validation scenarios. Still, most
scenarios share similarities, like, in that case, running MPI programs. PCVS
comes with default profiles for default scenarios. Here, we select the
`mpi` base profile to build our own:

.. code-block:: bash

	$ pcvs profile create user.my-profile --base mpi
	$ pcvs profile list

By specifying ``user.my-profile``, it will save the profile under ``~/.pcvs/`` and
make it available for the whole ``$USER``, no matter the current working
directory used when running PCVS. To learn more about profile scope, please see :ref:`profile-scope`.

.. note::
	As this profile uses MPI, we need to source an MPI implementation in the
	environment. Please use the method suiting your needs (spack/module/source).
	If interested in autoloading spack-or-module-based MPI implementation,
	please read :doc:`/ref/profile`.

Now, start PCVS. You must provide the profile & the directory where tests are
located:

.. code-block:: bash

	$ pcvs run --profile my-profile ./tests/

.. note::
	the ``user.`` prefix to the profile name may be removed as there is no
	name ambiguity, PCVS will detect the proper scope.

Access the results
##################

Results are stored in ``$PWD/.pcvs-build/rawdata/*.json`` by default. The
default output directory may be changed with `pcvs run --output`. JSON files can
directly process by third-party tools. The :download:`scheme
<../../../pcvs/schemes/test-result-scheme.yml>` can be used to update the input
parser with compliant output. Currently, PCVS only provides specific JSON format.
It is planned to support common validation format (like JUnit).

If no third-party tool is available, PCVS comes with a lightweight web server
(=Flask) to serve results in a web browser:

.. code-block:: bash

	# where pcvs run has been run:
	$ pcvs report
	# OR you may specify the run path
	$ pcvs report <path>

Then, browse http://localhost:5000/ to browse your results.
