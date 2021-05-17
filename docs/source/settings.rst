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
        cwd: path to build directory
        depends_on: 
            test: [list of tests on which it depends]
            spack: [list of spack dependencies used by this test]
            module: [list of installed modules this test needs]
        program: name of the binary file

The run node owns the ``iterate`` subnode which can contain custom iterators
desribed in the ``criterion`` node in the selected profile. Moreover, the
run.iterate node can define custom iterators without defining them in
``criterion`` by writing them in the run.iterate.program node.

.. code-block:: yaml

    run:
        iterate: 
            iterator_described_in_profile.runtime.criterion:
                values: [list of values for the corresponding iterator]
            program:
                custom_iterator: 
                    numeric: true/false
                    type: "argument" or "environment"
                    values: [list of values taken by the iterator]
                    subtitle: string chosen to identify this iterator

Validate
--------

The validate node describes the expected test behaviour, including exit, time
and matching output.


.. code-block:: yaml

    validate:
        expect_exit: expected exit code (integer)
        time:
            mean: expected time to compute the test (seconds / float) tolerance:
            standard deviation for expected time (seconds / float)
            kill_after: maximum time after which process has to be killed
            (seconds / float)
        match:
            label:
                expr:
                expect:
        script:
            path: Path to a validating script

Group
-----

Groups are described in profiles. They can contain ``build``, ``run``, ``tag``,
``validate``, and ``artifact`` subnodes. Once a group is defined in the used
profile it can be called in the validation setup file.

.. code-block:: yaml

    group: name of the group defined in the profile

Tag
---

Tags get in the results and tests can be sorted tag-wise. A test can have
multiple tags and tags do not have to be defined upstream.

.. code-block:: yaml

    tag: 
        - tag1
        - tag2

Artifact
--------

The artifact node contains anything the output should have in addition to the
results of tests.

.. code-block:: yaml

    artifact:
        obj1: "path/to/obj1"
        obj2: "path/to/obj2"