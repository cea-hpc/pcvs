****************
Validation setup
****************

Generalities
============

Setup files
-----------

Like profiles, setup configurations have nodes to describe different steps of
the process. These nodes are splitted into subnodes to describe the course of
the run.

The validation configuration is specified using setup files. These files can be
in the yml format, or be an executable files generating a yml configuration in
stdout. The informations of this configuration are crossed with the profile informations to

When PCVS is launched in a directory, it browses every subdirectory to find any
``pcvs.yml`` or ``pcvs.setup`` file and launches itself with the corresponding
configuration.

example
^^^^^^^

.. code-block::

    exampletree/
    ├── subdir1
    │   └── pcvs.yml
    └── subdir2
        └── pcvs.yml

Launching ```pcvs run exampletree`` will generate tests for subdir1/pcvs.yml
**and** for subdir2/pcvs.yml. There is no need to put a setup configuration in
the root of ``exampletree``, but it is possible to add a setup here.

Structure
=========

The yml input must have one node per test. Each test can describe the following
configurations :

* build
* run
* validate
* group
* tag
* artifact

Build
-----

The build node describe how a binary file should be built depending on its
sources. It contains the following subndoes :

.. code-block:: yaml

    build:
        files: path/to/the/file/to/build
        sources:
            binary: name of the binary to be built (if necessary)
        depends_on:
            test: [list of test names it depends on]
        
        cflags: extra cflags 
        ldflags: extra ldflags 
        cwd: directory where the binary should be built 
        variants: [list of variants (CF Configuration basic blocks -> compiler
        node)]

        autotools:
            params: [list of options for autotools]
        cmake:
            params: [list of options for cmake]
        make:
            target: target for make command

Run
---

The run node describes how a binary file should be launched. It contains the
following nodes :

.. code-block:: yaml

    run:
        program: name of the binary file
        iterate: 
            iterator_described_in_profile.runtime.criterion:
                values: [list of values for the corresponding iterator]