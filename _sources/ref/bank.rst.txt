#######
 Banks
#######

Banks save results of successive runs and retrieve themes.
They can be used to compare tests durations and test results from run to run
or to set dynamic validation time based on previous test to automatically catch performance regression.

A bank, contain multiples project, with each project containing multiples PCVS run results.
The project layer allows using the same bank for different PCVS run tests.
You can specify a project and a bank together with ``projectname@bankname``.
Banks are implemented as git repository, where each project is a git branch,
each PCVS run results is a commit and each unique test result is a file in the git tree.

.. note::

    As bank are git repository, they can be pushed & pull to be sync with a remote git repository.

Create, Manage or Delete a bank
###############################

To Create a bank, use the command:

.. code-block::

    pcvs bank init <bankname> <./bank/path>

.. note::

    If the folder already exist and is a valid bank git repository, you can use ``pcvs bank init`` to import it.

To delete a bank, use the command:

.. code-block::

    pcvs bank destroy <bankname>

.. note::

   The bank in only unlinked by bank destroy, to delete the repository completely, remove the folder containing the bank manually.

To list existing banks, use the command:

.. code-block::

    pcvs bank list


To show a bank, list theirs projects and count theirs saved runs:

.. code-block::

    pcvs bank show <bankname>


Feed a bank with results
########################


To load a test result in a ``.pcvs-build`` directory:

.. code-block::

    pcvs bank load


To save a ``.pcvs-build`` directory:

.. code-block::

    pcvs bank save <bankname>
    pcvs bank save <project@bankname> # to specify a project to save the data with


To run a test and directly save the result:

.. code-block::

    pcvs run --bank <project@bankname>

Test Validation
###############

To validate a test based on precedent runs results,
use the analysis plugin with the ``not_longer_than_previous_runs`` method
within a test description, see :ref:`test-validation`.

.. code-block::

    validate:
      analysis:
        method: not_longer_than_previous_runs
        args:
          history_depth: # nb of history to check in bank, default: 1
          tolerance: # tolerance compared to previous runs, in percent, default: 2%

Bank Graphs
###########

To plot graph of previous run, use the ``pcvs graph`` commands.
See examples below, use ``pcvs graph --help`` for arguments details.

.. code-block::

    pcvs graph project@bank --types rate --show
    pcvs graph project@bank --types all --path ./test_graph
    pcvs graph project@bank --types duration --path ./test_graph2 --limit 20 --ext "png"
