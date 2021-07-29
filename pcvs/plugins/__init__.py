import enum
import importlib
import inspect
import os
import pkgutil
import sys
from abc import abstractmethod

from pcvs.helpers import log
from pcvs.helpers.exceptions import PluginException


class Plugin:
    """Base class to inherit from when implementing a plugin.

    This class should be used by any defined plugin and:
    * the attribute ``step`` should be set to a possible value defined by
      :class:`Plugin.Step`.
    * implement the function ``run(self, *args, **kwargs)``

    List of possible values is defined by the per-step API.

    :raises PluginException.NotImplementedError: if run() method is not overriden
    """
    class Step(enum.Enum):
        """Possible pass a plugin can be loaded into.

        ``*_EVAL`` steps describe plugin passes where the function outcome can
        infer with the actual workflow.
        """
        INVALID = -1,

        START_BEFORE = enum.auto(),
        START_AFTER = enum.auto(),
        TFILE_BEFORE = enum.auto(),
        TDESC_BEFORE = enum.auto(),
        TEST_EVAL = enum.auto(),
        TDESC_AFTER = enum.auto(),
        TFILE_AFTER = enum.auto(),
        SCHED_BEFORE = enum.auto(),
        SCHED_SET_BEFORE = enum.auto(),
        SCHED_SET_EVAL = enum.auto(),
        SCHED_SET_AFTER = enum.auto(),
        SCHED_PUBLISH_BEFORE = enum.auto(),
        SCHED_PUBLISH_AFTER = enum.auto(),
        SCHED_AFTER = enum.auto(),
        END_BEFORE = enum.auto(),
        END_AFTER = enum.auto()

        def __str__(self):
            """Stringify a Step as a printable string

            :return: a printable string according to the step
            :rtype: str
            """
            return self.name

    step = Step.INVALID

    def __init__(self):
        """constructor method."""
        self._type = type(self)
        pass

    @abstractmethod
    def run(self, *args, **kwargs):
        """To-be-overriden method."""
        raise PluginException.NotImplementedError(type(self))


class Collection:
    """The Plugin Manager.

    Consists in a dict of passes, eaching being initialized to None. Only one
    plugin can be set to a given step (the last loaded).
    """

    def __init__(self):
        """constructor method"""
        self._plugins = {name: None for name in list(Plugin.Step)}

    def init_system_plugins(self):
        """Load plugins defined as ``pcvs-contrib`` module in current PYTHON env.
        """
        self.register_plugin_by_package("pcvs-contrib")

    def invoke_plugins(self, step, *args, **kwargs):
        """Load the appropriate plugin, given a step

        :param step: the step to target
        :type step: :class:`Plugin.Step`
        :raises PluginException.BadStepError: wrong Step value
        :return: the same return value as returned by the ``run()`` plugin method.
        :rtype: Any
        """
        if step not in list(Plugin.Step):
            raise PluginException.BadStepError(step)

        if self._plugins[step]:
            return self._plugins[step].run(*args, **kwargs)
        return None

    def has_step(self, step):
        """Check if a given pass is defined.

        :param step: the pass
        :type step: :class:`Step`
        :return: True if defined, False otherwise
        :rtype: bool
        """
        if step not in self._plugins:
            return False

        return self._plugins[step] is not None

    def show_plugins(self):
        """Display plugin context to stdout."""
        for step, elements in self._plugins.items():
            if len(elements) > 0:
                log.manager.print_section("Step {}:".format(str(step)))
                for e in elements:
                    log.manager.print_item("{}".format(type(e).__name__))

    def register_plugin_by_file(self, modpath):
        """Based on a filepath (as a module dir), load plugins contained in it.

        :param modpath: valid python filepath
        :type modpath: str
        """

        # the content is added to "pcvs-contrib" module
        spec = importlib.util.spec_from_file_location("pcvs-contrib",
                                                      modpath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.register_plugin_by_module(mod)

    def register_plugin_by_module(self, mod):
        """Based on a module name, load any defined plugin.

        mod must be a valid PYTHON module name.

        :param mod: module name
        :type mod: str
        """
        for (_, the_class) in inspect.getmembers(mod, inspect.isclass):
            if issubclass(the_class, Plugin) and the_class is not Plugin:
                step_str = str(the_class.step)
                class_name = the_class.__name__
                log.manager.debug(
                    "Loading {} ({})".format(class_name, step_str))
                if self._plugins[the_class.step]:
                    log.manager.info("{} overriden: {} -> {}".format(step_str,
                                     type(self._plugins[the_class.step]).__name__, class_name))

                self._plugins[the_class.step] = the_class()

    def register_plugin_by_dir(self, pkgpath):
        """From a prefix directory, load any plugin defined in it.

        Mainly used to load any Plugin classes defined in a directory. The
        directory must be layout'd as a PYTHON package.

        :param pkgpath: prefix path
        :type pkgpath: str
        """
        path = os.path.join(os.path.abspath(pkgpath), "..")
        pkgname = os.path.basename(pkgpath)

        sys.path.insert(0, path)
        self.register_plugin_by_package(pkgname)
        sys.path.remove(pkgpath)

    def register_plugin_by_package(self, pkgname):
        """Based on a package name, load any plugin defined into it.

        :param pkgname: package name, valid under current PYTHON env.
        :type pkgname: str
        :raises PluginException.LoadError: Error while importing the package
        """
        mod = __import__(pkgname)

        for _, name, ispkg in pkgutil.iter_modules(mod.__path__, mod.__name__ + "."):
            if not ispkg:
                try:
                    submod = importlib.import_module(name)
                    self.register_plugin_by_module(submod)
                except Exception as e:
                    raise PluginException.LoadError(name)
