Profiles
========

Generalities
------------

A PCVS profile defines a configuration in which PCVS will launch. This
configuration is divided in nodes, and it can be customized within pcvs or in
yaml files that can be imported/exported via the command line interface.

This configuration is separated in 5 nodes :

* compiler
* criterion
* group
* machine
* runtimes

Each node is separated in subnodes and can be defined separately in multiple
ways. As files, profiles are written with the yml syntax.

.. _profile-scope:

Scope
-----

Profiles can have different scopes depending on which user should have access or
which project should be affected by it. The 3 scopes are the following :

* Local : The profile is only seeable from a specific folder
* User : The profile is seeable from everywhere in an userspace.
* Global : The profile is accessible to everyone and from everywhere.

Building a new Profile
----------------------

To create a blank
profile, one can use the command :

.. code-block:: bash

    pcvs profile create example_profile

To export this profile in a file format, use the command :

.. code-block:: bash

    pcvs profile export example_profile example_profile.yml

This profile is fully customizable with any text editor, to import the profile
back into PCVS use the command :

.. code-block:: bash

    pcvs profile import example_profile example_profile.yml

Without arguments, the ``pcvs profile create`` command builds blocks as default,
but a profile can be built with custom configuration blocks.

Building a profile with existing configuration blocks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Building a profile based on configuration blocks can be done in two ways :

* in the CLI
* with the interactive mode

In the CLI
++++++++++

.. code-block:: bash

    pcvs profile create example_profile -b [scope].[block-name].[block-type]

This command has to include either 0 or 5 ``-b`` blocks (default or complete
configuration).

With the interactive mode
+++++++++++++++++++++++++

.. code-block:: bash

    pcvs profile create -i

For the configuration blocks setting please refer to the Configuration
blocks section.

Managing Profiles
-----------------

Besides being built, exported or imported, profiles can be altered or destroyed
with the corresponding commands.

Use pcvs profile list to see every available profiles.

``pcvs profile edit [profile]`` launches a text editor in order to manually
change the profile. PCVS scans editors to give a choice to users.
``pcvs profile edit -p [profile]`` to edit the plugin inside the profile.

``pcvs profile destroy [profile]`` deletes a profile.

Profiles are used at runtime, they are specified with the ``-p`` option.

.. code-block:: bash

    pcvs run -p example_profile
    pcvs run --profile-path /path/to/not/imported/profile
