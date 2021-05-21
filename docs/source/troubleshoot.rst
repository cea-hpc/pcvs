###############
Troubleshooting
###############

Building the tool
=================

Pygit2
------

Error message
^^^^^^^^^^^^^

While running ``pip3 install``, Such error messages are raised:

.. code-block:: bash

    -> error: git2.h: No such file or directory
    -> error: #error You need a compatible libgit2 version (1.1.x)

Solution(s)
^^^^^^^^^^^

- Manually install libgit2, version >= 1.0.0
- Use wheel package to install third-party tools

.. raw:: html

    <details><summary><strong>Explanation</strong></summary>

.. note::
    PCVS depends on pygit2 to deal with banks, pygit2 itself depending on
    libgit2 (libs & dev). It is possible to manually install libgit2 (both
    libs & dev), but be aware that pygit2 >= 1.2.0 requires libgit2 >=
    1.0.0. The latter may not be available on some systems, be sure to check
    out the proper version compatible with your pygit2 installation.

    Still, we recommend to rely on wheel packages to avoid installing extra
    third-party tools. `pip3` is the best solution. An important note: some
    `pip3` versions have issues when dealing with wheels, please ensure to
    update it before opening any ticket.

.. raw:: html

    </details>


Running the tool
================

TBW


