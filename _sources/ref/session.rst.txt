###################
Sessions
###################

About
#####

Start a new session
###################

.. code-block:: bash

    $ pcvs run <...> # start an interactive session
    $ pcvs run <...> --detach # start a background session

List sessions
#############

.. code-block:: bash

    $ pcvs session
    $ pcvs session -l

Cleanup
#######

Only for background sessions:

.. code-block:: bash

    $ pcvs session --ack <sid>
    $ pcvs session --ack-all # only completed sessions
