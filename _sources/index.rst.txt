.. PCVS-rt documentation master file, created by
   sphinx-quickstart on Tue Jul  7 10:46:45 2020. You can adapt this file
   completely to your liking, but it should at least contain the root `toctree`
   directive.

####################################
Parallel Computing Validation System
####################################

**Parallel Computing Validation System** (shorten to **PCVS**) is a Validation
Orchestrator designed by and for software at scale. Its primary target is HPC
applications & runtimes but can flawlessly address smaller use cases. PCVS can
help users to create their test scenarios and reuse them among multiples
implementations, a high value when it comes to validating Programmation
standards (like APIs & ABIs). No matter the number of programs, benchmarks,
languages, or tech non-regression bases use, PCVS gathers in a single execution,
and, with a focus on interacting with HPC batch managers efficiently, run jobs
concurrently to reduce the time-to-result overall. Through basic YAML-based
configuration files, PCVS handles more than hundreds of thousands of tests and
helps developers to ensure code production is moving forward.

While PCVS is a validation engine, not providing any benchmarks on its own, it
provides configurations to the most widely used MPI/OpenMP test applications
(benchmarks & proxy apps), constituting a 300,000+ test base, offering a new way
to compare implementations standard compliance.

PCVS acts as a bridge putting at scale regular test bases, by making the most of
the parallelism brought by HPC architectures, able to run thousands of tests at
the same time. This decrease in the time to result boosts productivity of
development, leading to a better software. By separating tests (=code to
execute) from application to validate, the effort of writing tests and setting
validation platform is strongly reduced, for instance:

#. The dev team writes tests and describes scenarii.
#. Cluster admins set up the architecture for testing (compilers, tools...).
#. Q/A dept. executes applications on given resource.

Splitting the effort will enforce reusability and flexibility. In many cases,
multiple test bases share same compilers, runtimes, tools or even machine
partition, it is then convenient (for administration purposes) to gather at a
higher level this type of responsibility.*

Using PCVS may have a slight cost as test logic must be converted to a new
semantics (not the tests themselves but the testing system behind it), without
being destructive for the original tests (PCVS can go together with other test
frameworks).

.. note::
   PCVS does not act as a test framework on its own. It does not have all the
   features from a test reporting interface either. Its purposes are to provide a
   new approach when building test-bases to dissociate testers from tested, to
   increase flexibility, reusability, ease maintenance and speed up test
   scheduling to minimize time to result. It is compatible with multiple build
   systems and test frameworks and can be integrated in a non-destructive way
   inside already-existing projects.

.. toctree::
   :maxdepth: 1
   :caption: Basics

   basics/features
   basics/getting-started
   basics/installation
   basics/basic-use
   basics/issues
   basics/workflow

.. toctree::
   :maxdepth: 1
   :caption: Reference

   ref/test-file
   ref/config
   ref/profile
   ref/session
   ref/utils
   ref/examples

..
   ref/run
   ref/report
   ref/test-file
   ref/config
   ref/profile
   ref/bank
   ref/session
   ref/utils
   ref/plugin
   ref/examples

.. toctree::
   :maxdepth: 1
   :caption: Development

   dev/contribution
   api/pcvs
..
   dev/overview
   dev/contribution
   api/pcvs
