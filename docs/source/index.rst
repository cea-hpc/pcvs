.. PCVS-rt documentation master file, created by
   sphinx-quickstart on Tue Jul  7 10:46:45 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

====================
PCVS Runtime toolkit
====================

PCVS Runtime Toolkit simplifies efforts of testing applications, especially when
it comes at scale. Most modern applications tested through a large set of tests
assessing their quality. To keep these test-suite easy to manage while continuously
growing the coverage, test frameworks are used to handle most basic scenarios, converting
the logic (=the effective test) to the actual code to execute (program, function...)

PCVS Runtime Toolkit acts as a bridge putting at scale regular test bases, by making
the most of the parallelism brought by HPC architectures, able to run thousands of tests
at the same time. This decrease in the time to result boosts productivity of development,
leading to a better software. By separating tests (=code to execute) from application to validate,
the effort of writing tests and setting validation plaform is strongly reduced:

* The dev team writes tests and describes scenarii
* Cluster admins sets up architecture for testing (compilers, tools, nodes...)
* Q/A dep. executes application tests on given resource

Splitting the effort will enforce reusability and flexibility. In many cases, multiple
test bases share same compilers, runtimes, tools or even machine partition, it is then
convenient (for administration purposes) to gather at a higher level this type of 
responsability.

Using PCVS may have a slight cost as test logic must be converted to a new semantics (not
the tests themselves but the testing system behind it), without being destructive for the
original tests (PCVS can go together with other test frameworks).

.. note::
   PCVS does not act as a test framework on its own. It does not have all the features
   from a test reporting interface either. Its purposes is to provide a new approach when
   building test-bases to dissociate testers from tested, to increase flexbility, reusability,
   ease maintenance and speed up test scheduling to minimize time to result. It is compatible
   with multiple build systems and test frameworks and can be integrated in a non-destructive way
   inside already-existing projects.

.. toctree::
   :maxdepth: 2
   :caption: Basics

   installation
   getting-started
   overview
   reporting

.. toctree::
   :maxdepth: 2
   :caption: Customizing

   config
   profile
   settings


.. toctree::
   :maxdepth: 2
   :caption: Reference

   glossary
   how-tos

