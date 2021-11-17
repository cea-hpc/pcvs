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
        self._plugins = {name: [] for name in list(Plugin.Step)}
        self._enabled = {name: None for name in list(Plugin.Step)}

    def register_default_plugins(self):
        """Detect plugins stored in default places."""
        try:
            self.register_plugin_by_package('pcvs-contrib')
        except:
            log.manager.info(
                "No pcvs-contrib package found for plugin autoloading")

    def activate_plugin(self, name):
        """Flag a plugin as active, meaning it will be called when the pass is
        reached.

        :param name: the plugin name.
        :type name: str"""
        for step, plugins in self._plugins.items():
            for p in plugins:
                if name == type(p).__name__:
                    log.manager.debug("Activate {}".format(name))
                    if self._enabled[p.step]:
                        log.manager.debug(
                            " -> overrides {}".format(self._enabled[p.step]))
                    self._enabled[p.step] = p
                    return
        log.manager.warn("Unable to find a plugin named '{}'".format(name))

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

        if self._enabled[step]:
            return self._enabled[step].run(*args, **kwargs)

        return None

    def nb_plugins_for(self, step):
        """Count the number of possible plugins for a given step.

        :param step: the step to check
        :type step: str

        :return: the number of plugins
        :rtype: int"""
        if step not in self._plugins:
            return -1

        return len(self._plugins[step])

    def has_enabled_step(self, step):
        """Check if a given pass is enabled.

        :param step: the pass
        :type step: :class:`Step`
        :return: True if defined, False otherwise
        :rtype: bool
        """
        if step not in self._enabled:
            return False
        return self._enabled[step] is not None

    def show_plugins(self):
        """Display plugin context to stdout."""
        for step, elements in self._plugins.items():
            if len(elements) > 0:
                log.manager.print_section("Step {}:".format(str(step)))
                for e in elements:
                    log.manager.print_item("{}".format(type(e).__name__))

    def show_enabled_plugins(self):
        """Display the list of loaded plugins."""
        empty = True
        for step, e in self._enabled.items():
            if e:
                empty = False
                log.manager.print_item(
                    "{}: {}".format(str(step), type(e).__name__))

        if empty:
            log.manager.print_item("None")

    def register_plugin_by_file(self, modpath, activate=False):
        """Based on a filepath (as a module dir), load plugins contained in it.

        :param modpath: valid python filepath
        :type modpath: str
        """

        # the content is added to "pcvs-contrib" module
        spec = importlib.util.spec_from_file_location("pcvs-contrib",
                                                      modpath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.register_plugin_by_module(mod, activate)

    def register_plugin_by_module(self, mod, activate=False):
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
                    "Register {} ({})".format(class_name, step_str))
                self._plugins[the_class.step].append(the_class())
                if activate:
                    self.activate_plugin(class_name)

    def register_plugin_by_dir(self, pkgpath, activate=False):
        """From a prefix directory, load any plugin defined in it.

        Mainly used to load any Plugin classes defined in a directory. The
        directory must be layout'd as a PYTHON package.

        :param pkgpath: prefix path
        :type pkgpath: str
        """
        path = os.path.join(os.path.abspath(pkgpath), "..")
        pkgname = os.path.basename(pkgpath)

        sys.path.insert(0, path)
        self.register_plugin_by_package(pkgname, activate)
        sys.path.remove(path)

    def register_plugin_by_package(self, pkgname, activate=False):
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
                    self.register_plugin_by_module(submod, activate)
                except Exception as e:
                    raise PluginException.LoadError(name)
