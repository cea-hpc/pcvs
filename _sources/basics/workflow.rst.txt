################
Common workflow
################

Per-project test infrastructure
###############################

Dedicated benchmark repository
##############################

Benchmark description
=====================

PCVS is a program built for current HPC structures, it allows the launch of
programs with a large coverage of parameters. Moreover, PCVS allows users to log
in and out streams and handle sessions. In order to do that, PCVS needs an
exhaustive configuration handled in files and profiles.

Validation profile
==================

Validation profiles are configuration files used at launch in pcvs run. A PCVS
validation profile can be generated with the following command :

.. code-block:: bash

    pcvs profile create tutorial_profile

A pcvs profile is made of blocks that can be customized, you can export a
profile to a file :

.. code-block:: bash

    pcvs profile export tutorial_profile tutorial_profile.yml

you should have a tutorial_profile.yml file which has the following nodes :

* compiler
* criterion
* group
* machine
* runtimes

Launch tests
============

Tests launches are done in this case by the following command :

.. code-block:: bash

    pcvs run -f -p tutorial_profile .

The generic command is :

.. code-block:: bash

    pcvs run [option] -p [profile] [directory]

PCVS will scan the target directory and find any "pcvs.yml" or "pcvs.setup" file
within the directory or its subdirectories, and launch the benchmark on the
corresponding files.

"pcvs.setup" files must return a yaml-structured character string describing a
pcvs configuration described in pcvs.yml files.

The pcvs run configuration is also structured in nodes, here is a typical
example:

.. code-block:: yaml

    tutorial_test:
        build:
            files: "@SRCPATH@/tutorial_program.c"
            sources:
                binary: "tutorial_binary"
        run:
            program: "tutorial_binary"

With a directory like such :

.. code-block:: bash

    ├── pcvs.yml
    └── tutorial_program.c

The run will :

* build ``tutorial_binary`` by compiling ``tutorial.c`` using gcc (as specified earlier)
* run the ``tutorial_binary`` file

Many other options are available such as tags, flags, etc, these are referenced in the documentation of PCVS.

Visualize results
=================

PCVS owns a HTML report generator, it can be used with :

.. code-block:: bash

    pcvs report

pcvs report must be used on a directory on which tests have been run.
