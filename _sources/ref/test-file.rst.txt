****************
Validation setup
****************

Generalities
============

Setup files
-----------

Like profiles, setup configurations have nodes to describe different steps of
the process. These nodes are split into subnodes to describe the course of
the run.

The validation configuration is specified using setup files. These files can be
in the yml format (``pcvs.yml``), or be an executable files (``pcvs.setup``)
generating a yml configuration in stdout.
The information of this configuration are crossed with the profile information
to run the tests.

When PCVS is launched in a directory, it browses every subdirectory to find any
``pcvs.yml`` or ``pcvs.setup`` file and launches itself with the corresponding
configuration.

Example
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
            cflags: extra cflags
            ldflags: extra ldflags
        depends_on: ["list of test names it depends on"]
        cwd: directory where the binary should be built
        variants: [list of variants (CF Configuration basic blocks -> compiler
        node)]

        autotools:
            params: [list of options for autotools]
        cmake:
            params: [list of options for cmake]
        make:
            target: target for make command
            jobs: make -j n option

Run
---

The run node describes how a binary file should be launched. It contains the
following nodes :

.. code-block:: yaml

    run:
        cwd: path to build directory
        depends_on: [list of tests on which it depends]
        package_manager:
            spack: [list of spack dependencies used by this test]
            module: [list of installed modules this test needs]
        program: name of the binary file

The run node owns the ``iterate`` subnode which can contain custom iterators
described in the ``criterion`` node in the selected profile. Moreover, the
``run.iterate`` node can define custom iterators without defining them in
``criterion`` by writing them in the run.iterate.program node.

.. code-block:: yaml

    run:
        iterate:
            iterator_described_in_'profile.runtime.criterion':
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
            hard_timeout: maximum time after which process has to be killed (seconds / float)
            soft_timeout: maximum time after which the test is considered failed (but can still finish, so you can run test correctness locally without testing optimisation (even on your slow computer))
        match:
            label:
                expr:
                expect:
        script:
            path: Path to a validating script
        method: name of the function in the plugin you  are using
            args: list of arguments for thefunction (see example below)
        method: 'not_longer_than_previous_runs' # check previous run in database
            args:
                history_depth: -1 # look at n previous run (-1 for all)
                tolerance: 10 # time can be 10% slower than the fastest of all previous runs

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


Setup file
==========

When using a ``pcvs.setup`` file, the file will be executed, and stdout should be
a valid yaml file that respect ``pcvs.yml`` file structure as describe above.

When running the script, some environment variables are availables to ease configuration.
The complete list of environment variables can be obtained by running ``pcvs -vvv run ...``.

The list is composed of:
  - Compilers environment variables starting with: ``PCVS_CMP``.
  - Criterions environment variables starting with: ``PCVS_CRIT``.
  - Other environment variables set in profile at ``compiler.compilers.<x>.envs``.

Example of availables environment variables: (will depends on your profile file)

.. code-block:: text


  PCVS_CMP_CC='gcc'
  PCVS_CMP_CC_ARGS=''
  PCVS_CMP_CC_VAR_OPENMP='gcc'
  PCVS_CMP_CC_VAR_OPENMP_ARGS='-fopenmp'
  PCVS_CMP_CUDA='nvcc'
  PCVS_CMP_CUDA_ARGS=''
  PCVS_CMP_CXX='g++'
  PCVS_CMP_CXX_ARGS=''
  PCVS_CMP_CXX_VAR_OPENMP='g++'
  PCVS_CMP_CXX_VAR_OPENMP_ARGS='-fopenmp'
  PCVS_CMP_FC='gfortran'
  PCVS_CMP_FC_ARGS=''
  PCVS_CMP_FC_VAR_OPENMP='gfortran'
  PCVS_CMP_FC_VAR_OPENMP_ARGS='-fopenmp'
  PCVS_CMP_HIP='hipcc'
  PCVS_CMP_HIP_ARGS=''

  PCVS_CRIT_N_CORE='1'
  PCVS_CRIT_N_MPI='1 2 4'
  PCVS_CRIT_N_NODE='1 2'
  PCVS_CRIT_N_OMP='1 4'
  PCVS_CRIT_N_PROC='1 4 8'

  PCVS_CC='gcc'
  PCVS_CXX='g++'
  PCVS_FC='gfortran'
  PCVS_HIPCC='hipcc'
  PCVS_NVCC='nvcc'
