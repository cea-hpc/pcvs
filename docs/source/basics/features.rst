##################
 Feature Overview
##################

Here is a quick overview of features that make PCVS a robust solution different
than other validation engines.

Run the validation from anywhere
################################

After installation, PCVS can be configured in a minute for the current directory:

.. code-block:: sh

    $ pcvs scan .
    $ pcvs run


Scale a test-suite depending on the target machine
##################################################

From PCVS approach, a benchmarks is a collection of programs. coupled with a
compiler and a launcher, sets of tests can be build to dynamically adapt the
machine to test. With a single edition, a test-suite can be ported from a
validating an MPI implementation on a simple workstation (no tests requiring
more than one node & 4-8 MPI processes) to largest supercomputers (thousands of
nodes). PCVS allow this thanks to **criterions**, a variadic component to apply
to a program to build tests. It may be populated as follows in a profile:

.. code-block:: yaml

    criterion:
        iterators:
            number_of_mpi_processes:
                values: [1, 2, 4, 8, 16, 32]

Automatic Test-suite builder
############################

PCVS relies on a specific test description syntax in order to build an efficient
test-suite. To help with that process, PCVS can pre-generate templates:

.. code-block:: sh

    $ pcvs scan /dir


Definition - Execution - Reporting in one place
###############################################

One main advantage of PCVS is the capability to gather all validation modules in
one single place, easy to install as a single user. Among others:

* Highly customizable test generation framework
* Orchestrator designed to run tests at scale
* Autonomous reporting web platform.
* Store results persistently as a Git repository for easy imports/exports &
  validatino progression.
