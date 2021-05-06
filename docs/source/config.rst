Configuration basic blocks
==========================

Generalities
------------
TBW

Scope
-----
TBW

Special: Runtime Configuration
------------------------------
compiler node 
^^^^^^^^^^^^^

The compiler node describes the building sequence of tests, from the compiler
command to options, arguments, tags, libraries, etc.

This node contains the following subnodes :

    commands :

        **cc** : compilation command for C code

        **cxx** : compilation command for C++ code

        **f77** : compilation command for Fortran77 code

        **f90** : compilation command for Fortran90 code

        **fc** : compilation command for generic Fortran code

    variants :

        cuda :

            **args** : additionnal arguments for code compiled with CUDA

        openmp :

            **args** : additionnal arguments for code compiled with openmp
            features

        strict :

            **args** : arguments for extra verifications

        tbb :

            **args** : arguments for use of tbb library

criterion node 
^^^^^^^^^^^^^^

the criterion node contains a collection of iterators that describe the tests.
PCVS can iterate over the following parameters :

* n_core * n_mpi * n_node * n_omp * n_proc

    iterators :

        n_[iterator] :

            **subtitle** : string used to indicate the number of [iterator] in
            the test description

            **values** : values that [iterator] allowed to take

Example
+++++++

iterators:
    n_core:
        **subtitle**: C

        **values**:
        
        - 1
        
        - 2


group node 
^^^^^^^^^^

The group node contains group definitions that describe tests. A group
description can contain any node present in the Configuration basic blocks (CF
Configuration basic blocks section).

Example
+++++++

    GRPMPI:
        run:
            iterate:
                n_omp:
                    **values**: null

machine node 
^^^^^^^^^^^^^^

The machine node describes the constraints of the physical machine. It lists
what processes can or can not use.

    machine :
        **nodes** : number of accessible nodes

        **cores_per_node** : number of accessible cores per node

        **concurrent_run** : maximum number of processes that can coexist

runtime node 
^^^^^^^^^^^^^^

The runtime node specifies entries that must be passed to the launch command. It
contains subnodes such as ``args``, ```iterators``, etc. The ``iterator`` node
contains arguments passed to the launching command. For example, if prterun
takes the "-np" argument, which corresponds to the number of MPI threads, let's
say ``n_mpi``, we will get the following runtime profile :

    **args** : arguments for the launch command

    iterators:
        n_mpi:
            **numeric** : true

            **option** : "-np "

            **type** : argument

            aliases :
                [dictionary of aliases for the option]
                
    plugins


