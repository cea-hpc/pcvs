#####################
 Contribution Guide
#####################

To contribute to pcvs, start by installing pcvs from the sources in a virtual
environment using the dev dependency as follows:

.. code-block:: bash

   python3 -m venv pcvs_env
   source ./pcvs_env/bin/activate
   git clone https://github.com/cea-hpc/pcvs.git pcvs
   cd pcvs
   pip install '.[dev]'

Then ensure precommits are setups & run them:

.. code-block:: bash

   pre-commit install --install-hooks

Make sure that the coverage tests, the linting and doc build works
before contributing:

.. code-block:: bash

   tox -e pcvs-coverage && tox -e pcvs-lint && tox -e doc
