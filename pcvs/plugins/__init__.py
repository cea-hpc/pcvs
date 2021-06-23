from abc import abstractmethod
import os
import sys
import inspect
import enum
import importlib
import pkgutil

from pcvs.helpers.exceptions import PluginException
from pcvs.helpers import log


class Plugin:
    
    class Step(enum.Enum):
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
            return self.name
            
    step = Step.INVALID
    
    def __init__(self):
        self._type = type(self)
        pass
    
    @abstractmethod
    def run(self, *args, **kwargs):
        raise PluginException.NotImplementedError(type(self))


class Collection:
    def __init__(self):
        self._plugins = {name: None for name in list(Plugin.Step)}
        
    def init_system_plugins(self):
        self.register_plugin_by_package("pcvs-contrib")
        
    def invoke_plugins(self, step, *args, **kwargs):
        if step not in list(Plugin.Step):
            raise PluginException.BadStepError(step)
        
        if self._plugins[step]:
            return self._plugins[step].run(*args, **kwargs)
        return None
        
    def has_step(self, step):
        if step not in self._plugins:
            return False
        
        return self._plugins[step] is not None
    def show_plugins(self):
        for step, elements in self._plugins.items():
            if len(elements) > 0:
                log.manager.print_section("Step {}:".format(str(step)))
                for e in elements:
                    log.manager.print_item("{}".format(type(e).__name__))
    
    def register_plugin_by_file(self, modpath):
        spec = importlib.util.spec_from_file_location("pcvs-contrib",
                                                      modpath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.register_plugin_by_module(mod)
        
    def register_plugin_by_module(self, mod):
        for (_, the_class) in inspect.getmembers(mod, inspect.isclass):
            if issubclass(the_class, Plugin) and the_class is not Plugin:
                step_str = str(the_class.step)
                class_name = the_class.__name__
                log.manager.debug("Loading {} ({})".format(class_name, step_str))
                if self._plugins[the_class.step]:
                    log.manager.info("{} overriden: {} -> {}".format(step_str, type(self._plugins[the_class.step]).__name__, class_name))
                
                self._plugins[the_class.step] = the_class()
                
    def register_plugin_by_dir(self, pkgpath):
        path = os.path.join(os.path.abspath(pkgpath), "..")
        pkgname = os.path.basename(pkgpath)
        
        sys.path.insert(0, path)
        self.register_plugin_by_package(pkgname)
        sys.path.remove(pkgpath)

    def register_plugin_by_package(self, pkgname):
        mod = __import__(pkgname)
        
        for _, name, ispkg in pkgutil.iter_modules(mod.__path__, mod.__name__ + "."):
                if not ispkg:
                    try:
                        submod = importlib.import_module(name)
                        self.register_plugin_by_module(submod)
                    except Exception as e:
                        raise PluginException.LoadError(name)
                    