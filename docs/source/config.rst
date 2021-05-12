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
informations.

Scope
-----

PCVS allows 3 scopes : 

* **global** for everyone on the machine having access to the PCVS installation
* **user** accessible from everywhere for the corresponding user 
* **local** accessible only from a directory

Blocks description
------------------

compiler node 
^^^^^^^^^^^^^

The compiler node describes the building sequence of tests, from the compiler
command to options, arguments, tags, libraries, etc.

This node can contain the subnodes **comands** and **variants**

commands
++++++++

The compiler.commands block contains a collection of compiler commands.

.. code-block:: yaml

    cc: compilation command for C code
    cxx: compilation command for C++ code
    f77: compilation command for Fortran77 code
    f90: compilation command for Fortran90 code
    fc: compilation command for generic Fortran code

variants
++++++++

The ``variants`` block can contain any custom variant. The variant must have a
**name**, and **arguments** as such :

.. code-block:: yaml

    example_variant:
        args: additionnal arguments for the example variant
    openmp:  
        args:  -fopenmp
    strict :
        args: -Werror -Wall -Wextra

I this example the variants "example_variant", "openmp", and "strict" have to be
specified in the validation setup where the user wants to use them.

criterion node 
^^^^^^^^^^^^^^

the criterion node contains a collection of iterators that describe the tests.
PCVS can iterate over custom parameters as such :

.. code-block:: yaml

    iterators :
        n_[iterator] :
            **subtitle** : string used to indicate the number of [iterator] in
            the test description

            **values** : values that [iterator] allowed to take

Example
+++++++


.. code-block:: yaml

    iterators:
        n_core:
            subtitle: C
            values:
            - 1
            - 2

In this case the program has to iterate on the core number and has to take the
values 1 and 2. The name ``n_core`` is arbitrary and has to be put in the
validation setup file.

group node 
^^^^^^^^^^

The group node contains group definitions that describe tests. A group
description can contain any node present in the Configuration basic blocks (CF
`Validation Setup` section).

Example
+++++++

.. code-block:: yaml

    GRPMPI:
        run:
            iterate:
                n_omp:
                    **values**: null

machine node 
^^^^^^^^^^^^

The machine node describes the constraints of the physical machine. 

machine :
    nodes : number of accessible nodes

    cores_per_node : number of accessible cores per node

    concurrent_run : maximum number of processes that can coexist

runtime node 
^^^^^^^^^^^^

The runtime node specifies entries that must be passed to the launch command. It
contains subnodes such as ``args``, ```iterators``, etc. The ``iterator`` node
contains arguments passed to the launching command. For example, if prterun
takes the "-np" argument, which corresponds to the number of MPI threads, let's
say ``n_mpi``, we will get the following runtime profile :


args : arguments for the launch command

.. code-block:: yaml

    iterators:
        n_mpi:
            numeric : true

            option : "-np "

            type : argument

            aliases :
                [dictionary of aliases for the option]
            
    plugins


