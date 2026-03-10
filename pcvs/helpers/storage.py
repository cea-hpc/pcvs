"""Helper package to find configuration and plugin files in pcvs configuration directories."""

import os
from enum import Enum
from pathlib import Path

from typing_extensions import Self

from pcvs import io
from pcvs import NAME_CONFIGDIR
from pcvs import PATH_HOMEDIR
from pcvs import PATH_INSTDIR

try:
    import rich_click as click

    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click  # type: ignore


class ConfigScope(Enum):
    """
    Storage Scope Enumeration.

    :var GLOBAL: pcvs installation path
    :var USER: user Home directory
    :var LOCAL: current testing directory
    """

    GLOBAL = 0
    USER = 1
    LOCAL = 2

    def __str__(self) -> str:
        """Convert to str."""
        return self.name.lower()

    def __repr__(self) -> str:
        """Convert to str."""
        return self.name

    @classmethod
    def fromstr(cls, scope: str) -> Self | None:
        """Get Scope from user str."""
        str_to_scope = {
            ConfigScope.GLOBAL.name: ConfigScope.GLOBAL,
            ConfigScope.USER.name: ConfigScope.USER,
            ConfigScope.LOCAL.name: ConfigScope.LOCAL,
        }
        return str_to_scope.get(scope.upper(), None)  # type: ignore

    @classmethod
    def all_scopes(cls) -> list[Self]:
        """Get all possible scopes."""
        all_scopes = [
            ConfigScope.LOCAL,
            ConfigScope.USER,
            ConfigScope.GLOBAL,
        ]
        return all_scopes  # type: ignore


class ConfigKind(Enum):
    """
    Configuration types.

    Associated with their config subdirectory and their default extension.
    """

    PROFILE = 0
    COMPILER = 1
    RUNTIME = 2
    MACHINE = 3
    CRITERION = 4
    GROUP = 5
    PLUGIN = 6

    def __str__(self) -> str:
        """Convert to str."""
        return self.name.lower()

    def __repr__(self) -> str:
        """Convert to str."""
        return self.name

    @classmethod
    def fromstr(cls, kind: str) -> Self | None:
        """Get Scope from user str."""
        str_to_kind = {
            ConfigKind.PROFILE.name: ConfigKind.PROFILE,
            ConfigKind.COMPILER.name: ConfigKind.COMPILER,
            ConfigKind.RUNTIME.name: ConfigKind.RUNTIME,
            ConfigKind.MACHINE.name: ConfigKind.MACHINE,
            ConfigKind.CRITERION.name: ConfigKind.CRITERION,
            ConfigKind.GROUP.name: ConfigKind.GROUP,
            ConfigKind.PLUGIN.name: ConfigKind.PLUGIN,
        }
        return str_to_kind.get(kind.upper(), None)  # type: ignore

    @classmethod
    def all_kinds(cls) -> list[Self]:
        """Get a list of all ConfigTypes."""
        all_kinds = [
            ConfigKind.PROFILE,
            ConfigKind.COMPILER,
            ConfigKind.CRITERION,
            ConfigKind.GROUP,
            ConfigKind.MACHINE,
            ConfigKind.RUNTIME,
            ConfigKind.PLUGIN,
        ]
        return all_kinds  # type: ignore

    @classmethod
    def get_file_ext(cls, ck: Self) -> str:
        """Get file type from ConfigType."""
        config_extensions = {
            ConfigKind.PROFILE: ".yml",
            ConfigKind.COMPILER: ".yml",
            ConfigKind.RUNTIME: ".yml",
            ConfigKind.MACHINE: ".yml",
            ConfigKind.CRITERION: ".yml",
            ConfigKind.GROUP: ".yml",
            ConfigKind.PLUGIN: ".py",
        }
        return config_extensions[ck]


class ConfigDesc:
    """An object to describe a config file."""

    def __init__(self, name: str, path: Path, kind: ConfigKind, scope: ConfigScope):
        """Initialize a Config file object description."""
        self._name: str = name
        self._path: Path = path
        self._kind: ConfigKind = kind
        self._scope: ConfigScope = scope

    @property
    def name(self) -> str:
        """The name of the config (with file extension)."""
        return self._name

    @property
    def path(self) -> Path:
        """The path of the config."""
        return self._path

    @property
    def kind(self) -> ConfigKind:
        """The type of the config."""
        return self._kind

    @property
    def scope(self) -> ConfigScope:
        """The scope of the config."""
        return self._scope

    @property
    def full_name(self) -> str:
        """Get the full name of the config."""
        return ":".join([str(self._scope), str(self._kind), self._name])

    @property
    def exist(self) -> bool:
        """Return if the file pointed by this config descriptor exist."""
        return self._path.is_file()

    def __eq__(self, other: object) -> bool:
        """Equality check (used in tsets)."""
        if not isinstance(other, ConfigDesc):
            return False
        return (
            self.name == other.name
            and self.path == other.path
            and self.kind == other.kind
            and self.scope == other.scope
        )

    def __repr__(self) -> str:
        """Representation Method."""
        return repr({"name": self.name, "path": self.path, "kind": self.kind, "scope": self.scope})


class ConfigLocator:
    """Helper to find and list config."""

    EXEC_PATH: str | None = None

    def __init__(self) -> None:
        """Init a Config Locator."""
        rel_exec_path = os.path.abspath(
            self.EXEC_PATH if self.EXEC_PATH is not None else os.getcwd()
        )
        self._storage_scope_paths: dict[ConfigScope, Path] = {
            ConfigScope.GLOBAL: Path(PATH_INSTDIR).joinpath("config"),
            ConfigScope.USER: Path(PATH_HOMEDIR),
            ConfigScope.LOCAL: Path(self.__get_local_path(rel_exec_path)),
        }

    @classmethod
    def __get_local_path(cls, path: str, subpath: str = NAME_CONFIGDIR) -> str:
        """Compute LOCAL Scope, get the first .pcvs directory in upper folders."""
        cur = path
        parent = "/"
        while not os.path.isdir(os.path.join(cur, subpath)):
            parent = os.path.dirname(cur)
            # Reach '/' and not found
            if parent == cur:
                cur = path
                break
            cur = parent
        # if we are in home dir, correct path is current working dir
        if os.path.join(cur, subpath) == PATH_HOMEDIR:
            cur = path
        return os.path.join(cur, subpath)

    def check_filename_ext(self, file_name: Path, kind: ConfigKind) -> Path:
        """Check of filename."""
        # check for missing extensions
        extension = ConfigKind.get_file_ext(kind)
        if file_name.suffix != extension:
            file_name = file_name.with_suffix(extension)
        return file_name

    def parse_scope_and_kind_raise(
        self,
        user_token: str,
    ) -> tuple[ConfigScope | None, ConfigKind | None]:
        """Parse scope[:kind] token, raise on failure."""
        res = self.parse_scope_and_kind(user_token)
        if isinstance(res, str):
            io.console.error(res)
            raise click.BadArgumentUsage(res)
        return res

    def parse_scope_and_kind(
        self, user_token: str, default_kind: ConfigKind | None = None
    ) -> tuple[ConfigScope | None, ConfigKind | None] | str:
        """Parse scope[:kind] token, return None on failure."""
        token = user_token.split(":")
        if len(token) == 1:
            scope, kind = ConfigScope.fromstr(token[0]), default_kind
            if scope is None:
                scope, kind = None, ConfigKind.fromstr(token[0])
                if kind is None:
                    return (
                        f"Invalid scope or kind, got '{user_token}', "
                        f"valid scope are: {ConfigScope.all_scopes()} "
                        f"and valid kind are: '{ConfigKind.all_kinds()}'"
                    )
                if default_kind is not None and kind != default_kind:
                    return f"Invalude kind, '{kind}' specify, needs '{default_kind}', in '{user_token}'"

            return (scope, kind)
        if len(token) == 2:
            scope, kind = ConfigScope.fromstr(token[0]), ConfigKind.fromstr(token[1])
            if scope is None:
                return f"Invalid config scope, got '{token[0]}', valid scopes are: {ConfigScope.all_scopes()}"
            if kind is None:
                return f"Invalid config kind, got '{token[1]}', valid kinds are: {ConfigKind.all_kinds()}"
            if default_kind is not None and kind != default_kind:
                return f"Invalude kind, '{kind}' specify, needs '{default_kind}', in '{user_token}'"
            return (scope, kind)
        return f"Bad user token, token should be 'scope[:kind]', got '{user_token}'"

    def parse_full_raise(
        self,
        user_token: str,
        kind: ConfigKind | None = None,
        should_exist: bool | None = None,
    ) -> ConfigDesc:
        """Parse use token and return and associated config file."""
        res = self.parse_full(user_token, kind, should_exist)
        if isinstance(res, str):
            io.console.error(res)
            raise click.BadArgumentUsage(res)
        return res

    def parse_full(
        self, user_token: str, kind: ConfigKind | None, should_exist: bool | None
    ) -> ConfigDesc | str:  # Config description and error
        """Parse [scope:[kind:]]label token."""
        # check for config scope & config kind
        scope = None
        token = user_token.split(":")
        if len(token) == 1:
            # config does not exist yet, but scope is not provided
            if should_exist is None or not should_exist:
                return (
                    "For a configuration that may not exist, specifying a scope is mandatory, "
                    f"error parsing: '{user_token}'"
                )
            # kind not provided, neither by token nor by function
            if kind is None:
                return f"Configuration kind not specify in user token: '{user_token}'."
            file_name = Path(user_token)
        elif len(token) == 2 or len(token) == 3:
            res = self.parse_scope_and_kind(":".join(token[:-1]), kind)
            if isinstance(res, str):
                return res
            scope, kind = res
            if scope is None:
                if should_exist is None or not should_exist:
                    return (
                        "For a configuration that may not exist, specifying a scope is mandatory, "
                        f"error parsing: '{user_token}'"
                    )
            if kind is None:
                return f"Fail to parse kind from token '{user_token}'"
            file_name = Path(token[-1])
        else:
            return f"Fail to parse scope (and kind), too many ':' in path '{user_token}'"

        assert kind is not None

        file_name = self.check_filename_ext(file_name, kind)

        if should_exist is True:
            return self.__get_existing_config(file_name, kind, scope)

        if should_exist is None:
            # May exist
            assert scope is not None
            return self.__get_may_exist_config(file_name, kind, scope)

        if should_exist is False:
            # should not exist
            assert scope is not None
            return self.__get_not_existing_config(file_name, kind, scope)

        return "Unreachable"

    def __get_existing_config(
        self, file_name: Path, kind: ConfigKind, scope: ConfigScope | None
    ) -> ConfigDesc | str:
        """Get a config, the config file must exist."""
        exist_config: ConfigDesc | None = self.find_config(file_name, kind, scope)
        if exist_config is None:
            return f"Config '{kind}:{file_name}' does not exist !"
        return exist_config

    def __get_may_exist_config(
        self, file_name: Path, kind: ConfigKind, scope: ConfigScope
    ) -> ConfigDesc | str:
        """Get a config, the config file may exist."""
        # search for config
        may_exist_config: ConfigDesc | None = self.find_config(file_name, kind, scope)
        if may_exist_config is not None:
            return may_exist_config
        config_path: Path = self.get_storage_path(file_name, kind, scope)
        no_config: ConfigDesc = ConfigDesc(config_path.stem, config_path, kind, scope)
        return no_config

    def __get_not_existing_config(
        self, file_name: Path, kind: ConfigKind, scope: ConfigScope
    ) -> ConfigDesc | str:
        """Get a config, the config file should not exist."""
        config_path: Path = self.get_storage_path(file_name, kind, scope)
        should_not_exist_config: ConfigDesc = ConfigDesc(config_path.stem, config_path, kind, scope)
        if should_not_exist_config.exist:
            return f"Config, '{should_not_exist_config.full_name}' already exist !"
        return should_not_exist_config

    def get_storage_dir(self, scope: ConfigScope, kind: ConfigKind | None = None) -> Path:
        """Get config dir from config scope and config type."""
        assert scope is not None
        config_dir: Path = Path(self._storage_scope_paths[scope])
        if kind:
            config_dir = config_dir.joinpath(str(kind).lower())
        return config_dir

    def get_storage_path(self, file_name: Path, kind: ConfigKind, scope: ConfigScope) -> Path:
        """Get config path from config label name, config type and config scope."""
        assert file_name is not None
        assert scope is not None
        assert kind is not None
        config_path: Path = self.get_storage_dir(scope, kind).joinpath(file_name)
        return config_path

    def find_config(
        self, file_name: Path, kind: ConfigKind, scope: ConfigScope | None = None
    ) -> ConfigDesc | None:
        """Get a config file description from it's name."""
        assert kind is not None
        scopes = ConfigScope.all_scopes() if scope is None else [scope]
        io.console.debug(
            f"Searching config for '{file_name}', of kind: '{kind}', in scopes: '{scopes}'"
        )
        for sc in scopes:
            config_path: Path = self.get_storage_path(file_name, kind, sc)
            io.console.debug(f"Looking for '{config_path}'.")
            config_path = self.check_filename_ext(config_path, kind)
            if config_path.is_file() and config_path.suffix == ConfigKind.get_file_ext(kind):
                io.console.debug(f"Found '{config_path}'.")
                return ConfigDesc(config_path.stem, config_path, kind, sc)
        return None

    def list_configs(self, kind: ConfigKind, scope: ConfigScope | None = None) -> list[ConfigDesc]:
        """List configs of type `ct` in scopes `cs`."""
        assert kind is not None
        scopes = ConfigScope.all_scopes() if scope is None else [scope]
        configs: list[ConfigDesc] = []
        for sc in scopes:
            configs_dir = self.get_storage_dir(sc, kind)
            for root, _, files in os.walk(configs_dir):
                for file in files:
                    config_path = Path(os.path.join(root, file))
                    if config_path.is_file() and config_path.suffix == ConfigKind.get_file_ext(
                        kind
                    ):
                        configs.append(ConfigDesc(config_path.stem, config_path, kind, sc))
        return configs

    def list_all_configs(self, scope: ConfigScope | None = None) -> list[ConfigDesc]:
        """List all configs types in all scopes."""
        configs: list[ConfigDesc] = []
        for ct in ConfigKind.all_kinds():
            configs += self.list_configs(ct, scope)
        return configs


def set_exec_path(exec_path: str) -> None:
    """Set EXEC_PATH."""
    ConfigLocator.EXEC_PATH = exec_path
