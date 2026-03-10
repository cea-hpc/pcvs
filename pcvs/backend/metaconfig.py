import os
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml import YAMLError

import pcvs
from pcvs import NAME_BUILDIR
from pcvs.backend.config import Config
from pcvs.backend.configfile import Profile
from pcvs.helpers import git
from pcvs.helpers import pm
from pcvs.helpers.exceptions import CommonException
from pcvs.helpers.validation import ValidationScheme
from pcvs.io import Verbosity

# Compiler to file extension mappings.
COMPILER_EXTENSION_CONFIG = {
    "cc": "\\.(h|H|i|I|s|S|c|c90|c99|c11)$",
    # ".h.H.i.I.s.S.c.c90.c99.c11"
    "cxx": "\\.(hpp|C|cc|cxx|cpp|c\\+\\+)$",
    # ".hpp.C.cc.cxx.cpp.c++"
    "fortran": "\\.(f|F)(77|90|95|(20)?(03|08)|c|C)?$",
    # ".f.F.f77.f90.f95.f03.f08.f2003.f2008.fc.fC.F77.F90.F95.F03.F08.F2003.F2008.Fc.FC"
    "cuda": "\\.(cu|CU)$",
    # ".cu.CU"
    "hip": "\\.(hip|HIP)$",
    # ".hip.HIP"
}


class MetaConfig(Config):
    """
    Root configuration object.

    It is composed of Config(), categorizing each configuration blocks.
    This MetaConfig() contains the whole profile along with
    any validation and current run information.
    This configuration is used as a dict extension.

    The internal_config is used to contain runtime information that should/could not be serialize.
    """

    def __init__(self, d: dict | None = None, internal_config: dict | None = None):
        """
        Init the object.

        :param d: items of the configuration
        :param internal_config: items to add to the internal_config

        internal_config is a subdictionnary for non serializable runtime object.
        The internal_config is therefore not save like the regular config.
        It act as a global variables registry.
        Using it is bad practice and should be avoided.
        """
        if d is None:
            d = {}
        if internal_config is None:
            internal_config = {}
        super().__init__(d)
        self.__internal_config = internal_config

    def bootstrap_from_profile(self, pf: Profile) -> None:
        """
        Bootstrap MetaConfig from profile.

        :param pf: The profile to bootstrap from.
        """
        self.bootstrap_compiler(pf.compiler)
        self.bootstrap_criterion(pf.criterion)
        self.bootstrap_group(pf.group)
        self.bootstrap_machine(pf.machine)
        self.bootstrap_runtime(pf.runtime)

    def bootstrap_compiler(self, conf: Config) -> None:
        """
        Specific initialize for compiler config.

        :param conf: compiler config to initialize
        """
        self.setdefault("compiler", conf)

        # check that configured compiler does exist.
        for compiler in conf["compilers"].values():
            # get correct extension if compiler is defined by type
            if "type" in compiler and "extension" not in compiler:
                ext = COMPILER_EXTENSION_CONFIG.get(compiler["type"], None)
                if ext is None:
                    # TODO: throw parsing errors
                    pass
                compiler["extension"] = ext
        if "package_manager" in conf:
            self.set_internal("cc_pm", pm.identify(conf["package_manager"]))

    def bootstrap_criterion(self, conf: Config) -> None:
        """
        Specific initialize for criterion config.

        :param conf: criterion config to initialize
        """
        self.setdefault("criterion", conf)

    def bootstrap_group(self, conf: Config) -> None:
        """
        Specific initialize for group config.

        :param conf: group config to initialize
        """
        self.setdefault("group", conf)

    def bootstrap_machine(self, conf: Config) -> None:
        """
        Specific initialize for machine config block.

        :param conf: machine config to initialize
        """
        self.setdefault("machine", conf)

        conf.setdefault("name", "default")
        conf.setdefault("nodes", 1)
        conf.setdefault("cores_per_node", 1)
        conf.setdefault("concurrent_run", 1)

        if "default_partition" not in conf or "partitions" not in conf:
            return

        # override default values by selected partition
        for elt in conf.get("partitions", []):
            if elt["name"] == conf["default_partition"]:
                conf.update(elt)
                break

        # redirect to direct programs if no wrapper is defined
        for kind in ["allocate", "remote", "batch"]:
            if not conf["job_manager"][kind]["wrapper"] and conf["job_manager"][kind]["program"]:
                conf["job_manager"][kind]["wrapper"] = conf["job_manager"][kind]["program"]

    def bootstrap_runtime(self, conf: Config) -> None:
        """Specific initialize for runtime config.

        :param conf: runtime config to initialize
        """
        self.setdefault("runtime", conf)
        if "package_manager" in conf:
            self.set_internal("rt_pm", pm.identify(conf["package_manager"]))

    def bootstrap_validation_from_file(self, filepath: str | None) -> None:
        """
        Specific initialize for validation config block.

        This function loads a file containing the validation dict.

        :param filepath: path to file to be validated
        :raises IOError: file is not found or badly formatted
        """
        node = {}
        if filepath is None:
            filepath = pcvs.PATH_VALCFG

        if os.path.isfile(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    node = YAML(typ="safe").load(fh)
            except (IOError, YAMLError) as e:
                raise CommonException.IOError(f"Error(s) found while loading {filepath}") from e

        conf: Config = Config(node)
        ValidationScheme("validation").validate(conf, filepath)

        # some post-actions
        for field in ["output", "reused_build"]:
            if field in conf:
                conf[field] = os.path.abspath(conf[field])

        if "dirs" in conf:
            conf["dirs"] = {k: os.path.abspath(v) for k, v in conf["dirs"].items()}

        self.bootstrap_validation(conf)

    def bootstrap_validation(self, conf: Config) -> Config:
        """
        Specific initialize for validation config.

        :param conf: The configuration to initialize
        :return: The initialized configuration.
        """
        self.setdefault("validation", conf)

        # Initialize default values when not set by user or default files
        conf.setdefault("verbose", str(Verbosity.COMPACT))
        conf.setdefault("print_policy", "none")
        conf.setdefault("color", True)
        conf.setdefault("default_profile", "default")
        conf.setdefault("output", os.path.join(os.getcwd(), NAME_BUILDIR))
        conf.setdefault("background", False)
        conf.setdefault("override", False)
        conf.setdefault("dirs", None)
        conf.setdefault("spack_recipe", None)
        conf.setdefault("simulated", False)
        conf.setdefault("anonymize", False)
        conf.setdefault("onlygen", False)
        conf.setdefault("timeout", None)
        conf.setdefault("target_bank", None)
        conf.setdefault("reused_build", None)
        conf.setdefault("webreport", None)
        conf.setdefault("only_success", False)
        conf.setdefault("enable_report", False)
        conf.setdefault("hard_timeout", 3600)
        conf.setdefault("soft_timeout", None)
        conf.setdefault("per_result_file_sz", 10 * 1024 * 1024)
        conf.setdefault("buildcache", os.path.join(conf["output"], "cache"))
        conf.setdefault("result", {"format": ["json"]})
        conf.setdefault(
            "author", {"name": git.get_current_username(), "email": git.get_current_usermail()}
        )

        if "format" not in conf["result"]:
            conf["result"]["format"] = ["json"]
        if "log" not in conf["result"]:
            conf["result"]["log"] = 1
        if "logsz" not in conf["result"]:
            conf["result"]["logsz"] = 1024

        return conf

    def set_internal(self, k: str, v: Any) -> None:
        """
        Manipulate the internal MetaConfig() node to store unexportable data.

        :param k: name of value to add
        :param v: value to add
        """
        self.__internal_config[k] = v

    def get_internal(self, k: str) -> Any:
        """
        Manipulate the internal MetaConfig() node to load unexportable data.

        :param k: key to get the associated value
        :return: valude associated to key k
        """
        if k in self.__internal_config:
            return self.__internal_config[k]
        return None


class GlobalConfig:
    """
    A static class to store a Global version of Metaconfig.

    To avoid carrying a global instancied object over the whole code, a
    class-scoped attribute allows to browse the global configuration from
    anywhere through `GlobalConfig.root`
    """

    root: MetaConfig = MetaConfig()
