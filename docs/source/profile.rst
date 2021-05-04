Profiles 
========

Generalitites 
-------------

A PCVS profile defines a configuration in which PCVS will launch. This
configuration is divided in nodes, and it can be customized within pcvs or in
yaml files that can be imported/exported via the command line interface.

This configuration is separated in 5 nodes :

* compiler * criterion * group * machine * runtimes

each node is separated in subnodes :

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

runtime node 
^^^^^^^^^^^^^^

Building a new Profile 
---------------------- 

TBW 

Managing Profiles 
----------------- 
TBW

Using Profiles 
--------------
