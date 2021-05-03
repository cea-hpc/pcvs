Profiles
========

Generalitites
-------------

A PCVS profile defines a configuration in which PCVS will launch. This
configuration is divided in nodes, and it can be customized within pcvs or in
yaml files that can be imported/exported via the command line interface.

This configuration is separated in 5 nodes :

* compiler
* criterion
* group
* machine
* runtimes

each node is separated in subnodes :

compiler node
^^^^^^^^^^^^^

    commands:
        cc: commande de compilation pour du code C

        cxx: commande de compilation pour du code C++

        f77: commande de compilation pour du code Fortran77

        f90: commande de compilation pour du code Fortran90

        fc: commande de compilation pour du code Fortran

    variants:

group node
^^^^^^^^^^

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
