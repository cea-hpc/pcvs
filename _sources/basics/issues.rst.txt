#############
Known issues
#############

Error installing Pygit2
#######################

Status: **Unresolved**

**Typical Error message**: While running ``pip3 install``, Such error messages
might be raised:

.. code-block:: bash

    -> error: git2.h: No such file or directory
    -> error: #error You need a compatible libgit2 version (1.1.x)

.. raw:: html

    <p><details><summary><strong>Click for an explanation.</strong></summary>
    <p>PCVS depends on pygit2 to deal with banks, pygit2 itself depending on
    libgit2 (libs & dev). It is possible to manually install libgit2 (both libs
    & dev), but be aware that <code>pygit2 >= 1.2.0</code> requires
    <code>libgit2 >= 1.0.0</code>. The latter may not be available on some
    systems, be sure to check out the proper version compatible with your pygit2
    installation.</p>
    <p>Still, we recommend relying on wheel packages to avoid
    installing extra third-party tools. <code>pip3</code> is the best solution.
    </p></details></p>

Solution / Workaround
*********************

- Manually install libgit2, version >= 1.0.0
- Use wheel package to install third-party tools
