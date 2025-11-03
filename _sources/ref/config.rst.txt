Configuration basic blocks
==========================

Generalities
------------

Configuration blocks define settings for PCVS. There are 5 configurable blocks
which are :

* compiler
* criterion
* group
* machine
* runtime

The configuration block is a virtual object, it doesn't exist per se,
configuration blocks are used to build profiles which can be imported/exported.
It is possible however to share configuration blocks by addressing them in a
scope that is large enough to reach other users.

Each configuration block contains sub-blocks in order to isolate and classify
information.

Scope
-----

PCVS allows 3 scopes :

* **global** for everyone on the machine having access to the PCVS installation
* **user** accessible from everywhere for the corresponding user
* **local** accessible only from a directory

Blocks description
------------------

compilers node
^^^^^^^^^^^^^^

The compiler node describes how to use a compiler, it include the following nodes:
* ``program``: the name of the program to execute
* ``envs``: the env to export at build time for that compiler, useful if you are using a Makefile
* ``extension``: the source code extension match by the compilers.
* ``variants``: different version of the same compiler configuration entry.


compilers node example
++++++++++++++++++++++

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

criterion node
^^^^^^^^^^^^^^

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

Group node
^^^^^^^^^^

The group node contains group definitions that describe tests. A group
description can contain any node present in the Configuration basic blocks (CF
`Validation Setup` section).

Example
+++++++

The following example allow you to disable the ``n_omp`` criterion of the group ``GRPMPI``.

.. code-block:: yaml

    GRPMPI:
        run:
            iterate:
                n_omp:
                    **values**: null

machine node
^^^^^^^^^^^^

The machine node describes the constraints of the physical machine.

.. code-block:: yaml

    machine:
        nodes: number of accessible nodes
        cores_per_node: number of accessible cores per node
        concurrent_run: maximum number of processes that can coexist

runtime node
^^^^^^^^^^^^
``program`` specify a wrapper for runtime tests, such as ``mpirun`` for example.
The ``compiling.wrapper`` specify a wrapper for test compilation.
It can be use to run the compilation on an other node using ``srun`` for example.

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
