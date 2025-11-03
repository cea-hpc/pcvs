#####################
 Utilities
#####################

Run a single test
#################

.. code-block:: bash

    $ pcvs exec <fully-qualified test-name>
    $ pcvs exec --show [cmd|env|loads|all] <test-name>


Input correctness
#################

Profiles
********

.. code-block:: bash

    $ pcvs check --profiles

Configuration blocks
********************

.. code-block:: bash

    $ pcvs check --configs

Test-suites
***********

.. code-block:: bash

    $ pcvs check --directory <path>


Discover tests & generate proper configurations
###############################################

.. code-block:: bash

    $ pcvs scan <path>


Build & artifacts cleanup
#########################

.. code-block:: bash

    $ pcvs clean --dry-run # list content to be deleted, recursively
    $ pcvs clean --force # actually deleting content
