.. _tuto:

########
Tutorial
########

Quick Install
#############

The source code is available on GitHub. To check out the latest release:
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


Once PCVS is installed, the ``pcvs`` executable is available in ``PATH``.
This program is the only entry point to PCVS:

.. code-block:: sh

 $ pcvs

 Usage: pcvs [OPTIONS] COMMAND [ARGS]...

 PCVS main program.

   Options
  --verbose           -v        INTEGER RANGE  Enable PCVS verbosity (cumulative) [env var: PCVS_VERBOSE]
  --debug             -d                       Enable Debug mode (implies `-vvv`) [env var: PCVS_DEBUG]
  --color/--no-color  -c                       Use colors to beautify the output [env var: PCVS_COLOR]
  --glyph/--no-glyph  -g                       enable/disable Unicode glyphs [env var: PCVS_ENCODING]
  --exec-path         -C        DIRECTORY      [env var: PCVS_EXEC_PATH]
  --version           -V                       Display current version
  --plugin-path       -P        PATH           Default Plugin PATH [env var: PCVS_PLUGIN_PATH]
  --plugin            -m        TEXT           Default plugin names to enables.
  --tui               -t                       Use a TUI-based interface. [env var: PCVS_TUI]
  --help              -help,-h                 Show this message and exit.

   Commands
  bank                      Persistent data repository management
  check                     Ensure future input will be compliant with standards
  clean                     Remove artifacts generated from PCVS
  config                    Manage Configurations
  convert                   YAML to YAML converter
  exec                      Running aspecific test
  graph                     Export graph from tests results.
  remote-run                Internal command to re-run a PCVS instance. Should not be used directly
  report                    Manage PCVS result reporting interface
  run                       Run a validation
  scan                      Analyze directories to build up test conf. files
  session                   Manage multiple validations



.. _tuto_test-desc:

Create tests descriptions
#########################

Before using PCVS, let's consider a provided test-suite in a ``tests/`` directory
(:download:`all-reduce.c <../examples/all-reduce.c>` & :download:`wave.c <../examples/wave.c>` provided for convenience):
With a directory like such:

.. code-block:: bash

    $ tree tests
    tests
    ├── coll
    │   └── all-reduce.c
    ├── pcvs.yml
    └── pt2pt
        └── wave.c

PCVS needs rules to know how to parse the test-suite above to create tests.
This will be done through ``pcvs.yml`` specification file.
Such a file can be placed anywhere in the file tree.
Consider putting it directly under the ``tests/`` directory for this example.

.. note::
    A test is the combination of a program, its arguments and the environment used to execute it.
    From PCVS' point of view, a test file does not carry the whole test environment.
    Thus, ``pcvs.yml`` expects the user to describe programs to be used to build the test-suite.

A basic ``pcvs.yml`` file for our tests may look like this:

.. literalinclude:: ../examples/pcvs.yml
    :language: yaml

This file specifies two root nodes referred as *Test Expressions* (TE) or *Test Descriptors* (TD).
It contains subondes describing how to build programs.
The ``build`` node gives information about how to build the program.
``files`` (a list *or* a string) contains the whole list of files required to build the program (in this case a C file).
With no other information, PCVS will assume the program to be built with a compiler (no invocation to a build system here).
A ``run`` subnode instructs PCVS to execute the program.
This is the simplest way to integrate tests to PCVS.

PCVS also supports building programs through Make, CMake & Autotools, each system
having its own set of keys to configure:

* ``build.make.target``: allow configuring a Make target to invoke.
* ``build.cmake``: for cmake configurations.
* ``build.autotools.params``: configure script flags
* ``build.autotools.autogen``: boolean whether to execute autogen.sh first.

By default, a test is considered valid if its exit code is 0.
The ``validate`` node allow modifying the validation process depending on
return code, stdout content, execution time, etc...

Many other options are available such as group, tags, flags, artifact, metrics, attributes, etc...
For more detailed documentation on test setup, consult: :ref:`test-file`.
For a complete list of nodes to be used in a ``pcvs.yml``, please consult :ref:`te-format`.

.. warning::
    Beware of tabulations, YAML indentations only supports spaces !

Proper YAML formats can be checked with:

.. code-block:: bash

    $ pcvs check --directory tests

Jobs can also be described using a ``pcvs.setup`` file, which must return a
yaml-structured character string describing a valid pcvs configuration as would
a ``pcvs.yml``.

.. _tuto_config:

Create a configuration profile
##############################

Validation profiles are configuration files used at launch by ``pcvs run``.
A profile contains link to part of the whole PCVS configuration.
This approach allow flexibility for complex configurations.
A complete configuration is composed of 5 configurations:
``compiler``, ``criterion``, ``group``, ``machine`` & ``runtime``.
For full configuration details, look at :ref:`config`.

To list all available default ``profile`` and ``configuration``, use:

.. code-block:: bash

    $ pcvs config list

For this example, we will target a simple MPI implementation.
To create the most basic profile able to run MPI programs,
we may herit ours from the provided ``mpi`` configuration:

.. code-block:: bash

    $ pcvs config create user:profile:myprofile --clone global:profile:mpi

By specifying ``user:profile``, it will save the profile under ``~/.pcvs/profile`` and
make it available for the whole ``$USER``, no matter the current working
directory used when running PCVS. To learn more about profile scope, please see :ref:`config-scope`.

This profile can be references with ``user:profile:myprofile``
(or ``profile:myprofile`` in short, where there are no possible conflicts).

A profile can be edited if necessary with ``pcvs config edit profile:myprofile``.
It will open an ``$EDITOR``.
When exiting, the profile is validated to ensure coherency.
In case it does not fulfill a proper format, a rejection file is crated in the current directory.
Once fixed, the profile can be saved as a replacement with:

.. code-block:: sh

    $ pcvs profile import newprofile --force --source user_profile_myprofile_rejected_0_.yml

.. warning::
    The ``--force`` option will overwrite any profile with the same name, if it exists.
    Please use this option with care.
    In case of a rejection, the import needs to be forced in order to replace the old one.

If profiles are edited directly, proper YAML formats can be checked before ``pcvs`` execution with:

.. code-block:: sh

    $ pcvs check --profiles

Execute the tests
#################

PCVS relies on test specifications (:ref:`tuto_test-desc`) and execution profile
(:ref:`tuto_config`) to create and execute a full benchmarks.

To start PCVS, you must provide the profile & the directory where tests are located:

.. code-block:: bash

    $ pcvs run --profile myprofile ./tests/

.. note::

    A list of directories can also be given to the command.

.. note::

    The ``user:`` prefix to the profile name may be removed as there is no
    name ambiguity, PCVS will detect the proper scope.

.. note::

    If no profile argument is provided, PCVS will look for a profile named ``default``.

Once started, the validation process is logged under ``$PWD/.pcvs-build`` directory.
If the directory already exists, it is cleaned up and reused.
A lock is put in that directory to protect against concurrent PCVS execution in the same directory.

When the ``pcvs run`` command is run, PCVS will recursively scan the target directory,
find any ``pcvs.yml`` or ``pcvs.setup`` file within the directory
or its subdirectories to launch the corresponding tests.

PCVS will:

* run ``pcvs.setup`` file to generate associated ``pcvs.yaml`` file.
* parse ``pcvs.yaml`` file to generate tests to run.
* build ``all_reduce`` & ``wave`` by compiling their corresponding c file
  using the compiler provided by the compiler configuration of ``myprofile``.
* run the ``all_reduce`` & ``wave`` program as many times as describes by criterions.

Access the results
##################

Results are stored in ``$PWD/.pcvs-build/rawdata/*.json`` by default.
The default output directory may be changed with ``pcvs run --output``.
JSON files can directly process by third-party tools.
The :download:`scheme <../../../pcvs/schemes/test-result-scheme.yml>`
can be used to update the input parser with compliant output.

PCVS comes with 2 way to visualize the results.
A lightweight web server (using Flask) to serve results in a web browser.

.. code-block:: bash

    # where pcvs run has been run:
    $ pcvs report
    # OR you may specify the run path
    $ pcvs report <path>


.. note::

    Browse to http://localhost:5000/ to see your results.

Or a tui using textual:

.. code-block:: bash

    # to use the tui
    $ pcvs --tui report
