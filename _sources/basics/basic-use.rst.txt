##############
 Basic usage
##############

Once PCVS is installed through the :ref:`installation-guide`, the ``pcvs`` is
available in ``PATH``. This program is the only entry point to PCVS:

.. code-block:: sh

 $ pcvs

 Usage: pcvs [OPTIONS] COMMAND [ARGS]...

 PCVS main program.

   Options
  --verbose      -v             INTEGER RANGE  Enable PCVS verbosity (cumulative) [env var: PCVS_VERBOSE]
  --debug        -d                            Enable Debug mode (implies `-vvv`) [env var: PCVS_DEBUG]
  --color        -c/--no-color                 Use colors to beautify the output [env var: PCVS_COLOR]
  --glyph        -g/--no-glyph                 enable/disable Unicode glyphs [env var: PCVS_ENCODING]
  --exec-path    -C             DIRECTORY      [env var: PCVS_EXEC_PATH]
  --version      -V                            Display current version
  --plugin-path  -P             PATH           Default Plugin path prefix [env var: PCVS_PLUGIN_PATH]
  --plugin       -m             TEXT
  --tui          -t                            Use a TUI-based interface. [env var: PCVS_TUI]
  --help         -help,-h                      Show this message and exit.

   Commands
  bank                      Persistent data repository management
  check                     Ensure future input will be compliant with standards
  clean                     Remove artifacts generated from PCVS
  config                    Manage Configuration blocks
  convert                   YAML to YAML converter
  exec                      Running aspecific test
  graph                     Export graph from tests results.
  profile                   Manage Profiles
  remote-run                Internal command to re-run a PCVS instance. Should not be used directly
  report                    Manage PCVS result reporting interface
  run                       Run a validation
  scan                      Analyze directories to build up test conf. files
  session                   Manage multiple validations

Create a profile
################

A profile contains the whole PCVS configuration in a single place. While
this approach allow deeply complex approaches, we will target a simple MPI
implementation for this example. To create the most basic profile able to run
MPI programs, we may herit ours from pre-generated called a template:

.. code-block:: sh

    $ pcvs profile create -t mpi user.myprofile

This profile can not be references with `user.myprofile` (or `myprofile` in
short, where there are no possible conflicts. This profile will be available at
user-level scope. It is also possible to set this profile as ``local`` (only for
the current directory or ``global`` (anyone using the PCVS installation)). You may
replace ``newprofile`` by a name of your choice.
For a complete list of available templates, please check ``pcvs profile list --all``.

A profile can be edited if necessary with ``pcvs profile edit newprofile``. It
will open an ``$EDITOR``. When exiting, the profile is validated to ensure
coherency. In case it does not fulfill a proper format, a rejection file is
crated in the current directory. Once fixed, the profile can be saved as a
replacement with:

.. code-block:: sh

    $ pcvs profile import newprofile --force --source file.yml

.. warning::
    The ``--force`` option will overwrite any profile with the same name, if it
    exists. Please use this option with care. In case of a rejection, the import
    needs to be forced in order to replace the old one.

Implement job descriptions
###########################

For a short example of implementing test descriptions, please refer to the
:ref:`test-suite-layout` shown in the :ref:`getting-started` guide. A more
detailed presentation of test description capabilities is available in its
own documentation page.

The most basic ``pcvs.yml`` file may look like this:

.. code-block:: yaml

    my_program:
        build:
            files: ['main.c']
        run:
            program: ['a.out']

PCVS also supports building programs through Make, CMake & Autotools, each system
having its own set of keys to configure:

* ``build.make.target``: allow configuring a Make target to invoke.
* ``build.cmake.vars``: variables to forward to cmake (to be prefixed w/ ``-D``)
* ``build.autotools.params``: configure script flags
* ``build.autotools.autogen``: boolean whether to execute autogen.sh first.

Proper YAML formats can be checked before running a test-suite with:

.. code-block:: sh

    $ pcvs check --directory /path/to/dir
    $ pcvs check --profiles

Run a test-suite
################

Start a run from the local directory with our profile is as simple as:

.. code-block:: sh

    $ pcvs run --profile newprofile

A list of directories can also be given. Once started, the validation process is
logged under ``$PWD/.pcvs-build`` directory. If the directory already exists, it
is cleaned up and reused. A lock is put in that directory to protect against
concurrent PCVS execution in the same directory.
