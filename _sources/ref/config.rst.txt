Configurations
==============

Generalities
------------

Configurations define settings for PCVS. There are 5 basic configurations files
which are:

* compiler
* criterion
* group
* machine
* runtime

One of each configuration are used to build a **profile**.
The profile is the top level configuration used to run pcvs.

Scope
-----

PCVS allows 3 scopes:

* **local** accessible only from a specific ``.pcvs`` folder.
    The **local** folder is defined as the first ``.pcvs`` folder found walking up
    the file system tree from the execution directory of pcvs.
* **user** accessible from everywhere for the corresponding user, store in ``~/.pcvs``
* **global** for everyone on the machine having access to the PCVS installation.
    **global** configuration are read only, they are stored in the pcvs installation and
    override at each pcvs install. This scope is used to ship default configurations
    that can be used directly or as template for creating your own configuration in user or local scope.

Command usage
-------------

To list existing configurations, use the command:

.. code-block:: bash

    $ pcvs config list

To create a config, one can use the command:

.. code-block:: bash

    $ pcvs config create user:example_profile

By default, the new configuration will contain the default configuration block for your configuration type.
To copy from another configuration block, use:

.. code-block:: bash

    $ pcvs config create --clone global:compiler:gcc user:compiler:mygcc

This configuration is fully customizable with any text editor, to edit the configuration, use the command:

.. code-block:: bash

    $ pcvs config edit profile:example_profile

To export or import configuration, use the command:

.. code-block:: bash

    $ pcvs config export profile:default --output test.yml
    $ pcvs config import user:profile:default_copy --source test.yml

To delete a configuration, use the command:

.. code-block:: bash

    $ pcvs config destroy <configuration_name>


Files architecture
------------------

For each storage scope, configurations are stored in files in a tree like structure
and can be edited manually for automation.

.. warning::

    When edited manually, pcvs will not be able to check and validate your configuration.
    Using ``pcvs config edit`` is preferred.

.. code-block::

    ~/.pcvs
    ├── compiler
    │   ├── default.yml
    │   ├── gcc.yml
    │   └── mpi.yml
    ├── criterion
    │   ├── default.yml
    │   └── mpi.yml
    ├── group
    │   ├── common.yml
    │   └── default.yml
    ├── machine
    │   ├── default.yml
    │   └── slurm.yml
    ├── plugin
    │   ├── default.py
    │   └── mpi.py
    ├── profile
    │   ├── default.yml
    │   ├── gcc.yml
    │   └── mpi.yml
    └── runtime
        ├── default.yml
        └── mpi.yml


.. _profile-scope:

Profile
-------

A PCVS **profile** is the root configuration block that link all configurations together
and need to be provided to pcvs to run a test suite.
A profile contain 5 references, to one of each of the configuration types.
It will look like that:

.. code-block:: yaml

    compiler: local:gcc
    criterion: global:default
    group: default
    machine: mycluster.yml
    runtime: default

**Scopes** can be optionally provided.
If not provided, all scope are check in order **local** -> **user** -> **global**.
File extensions are optionnals.

Configuration description
-------------------------

Compilers configuration
^^^^^^^^^^^^^^^^^^^^^^^

The compiler node describes how to use a compiler, it includes the following nodes:
* ``program``: the name of the program to execute
* ``envs``: the env to export at build time for that compiler, useful if you are using a Makefile
* ``extension``: the source code extension match by the compilers.
* ``variants``: different version of the same compiler configuration entry.


Compilers example
+++++++++++++++++

The ``compiler.compilers`` block contains a collection of compiler configurations.

.. code-block:: yaml

  compilers:
    cc:
      program: mpicc
      envs: [PCVS_CC=mpicc]
      extension: "\\.(h|H|i|I|s|S|c|c90|c99|c11)$"
      variants: &openmp
        openmp:
          args: [-fopenmp]
    cxx:
      program: mpicxx
      envs: [PCVS_CXX=mpicxx]
      extension: "\\.(hpp|C|cc|cxx|cpp|c\\+\\+)$"
      variants: *openmp
    f77:
      program: mpif77
      envs: [PCVS_FC=mpif77]
      extension: "\\.(f|F)(77)?$"
      variants: *openmp
    f90:
      program: mpif90
      envs: [PCVS_FC=mpif90]
      extension: "\\.(f|F)(90)?$"
      variants: *openmp
    fc:
      program: mpifort
      envs: [PCVS_FC=mpifort]
      extension: "\\.(f|F)(95|(20)?(03|08)|c)?$"
      variants: *openmp

variants
++++++++

The ``variants`` block can contain any custom variant.
The variant must have a **name**, and **arguments** as such:

.. code-block:: yaml

    example_variant:
        args: additional arguments for the example variant
    openmp:
        args: -fopenmp
    strict:
        args: -Werror -Wall -Wextra

In this example the variants "example_variant", "openmp", and "strict" have to be
specified in the validation setup where the user wants to use them.

Criterion configuration
^^^^^^^^^^^^^^^^^^^^^^^

The criterion node contains a collection of iterators that describe the tests.
PCVS can iterate over custom parameters as such :

.. code-block:: yaml

    iterators :
        n_[iterator] :
            **subtitle** : string used to indicate the number of [iterator] in the test description
            **values** : values that [iterator] allowed to take

Example
+++++++


.. code-block:: yaml

    iterators:
        n_core:
            subtitle: C
            values: [1, 2]

In this case the program has to iterate on the core number and has to take the
values 1 and 2. The name ``n_core`` is arbitrary and has to be put in the
validation setup file.

Group configuration
^^^^^^^^^^^^^^^^^^^

The group node contains group definitions that describe tests. A group
description can contain any node present in the Configuration basic blocks (CF
`Validation Setup` section).

Example
+++++++

The following example allows disabling the ``n_omp`` criterion of the group ``GRPMPI``.

.. code-block:: yaml

    GRPMPI:
        run:
            iterate:
                n_omp:
                    **values**: null

Machine configuration
^^^^^^^^^^^^^^^^^^^^^

The machine node describes the constraints of the physical machine.

.. code-block:: yaml

    machine:
        nodes: number of accessible nodes
        cores_per_node: number of accessible cores per node
        concurrent_run: maximum number of processes that can coexist

Runtime configuration
^^^^^^^^^^^^^^^^^^^^^
``program`` specify a wrapper for runtime tests, such as ``mpirun`` for example.
The ``compiling.wrapper`` specify a wrapper for test compilation.
It can be used to run the compilation on another node using ``srun`` for example.

The ``criterions`` node contains arguments passed to the launching command.
For example, if ``prterun`` takes the "-np" argument, which corresponds
to the number of MPI threads, let's say ``n_mpi``,
we will get the following runtime profile:

``plugins`` specify a python plugin that will be loaded and use to filter
available criterions. ``defaultplugin`` specify the name of one of the default
plugin to use.

``args`` specify static arguments to ``program``.

.. code-block:: yaml

    program:
    compiling:
      wrapper:
    args:
    plugin:
    defaultplugin:
    criterions:
        n_mpi:
            numeric: true
            option: "-np"
            type: argument
            aliases:
                [dictionary of aliases for the option]

Plugin
++++++

Runtime reference a plugin configuration.
The plugin configuration is a python plugin with a function to filter valid criterions.

.. warning::
   When cloning a plugin with ``pcvs create --clone`` make sure to rename the
   Class in the plugin. Otherwise, only one of the 2 plugins with the same name
   will be loaded.
