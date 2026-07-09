import os
from pathlib import Path

from pcvs.helpers.storage import ConfigDesc
from pcvs.helpers.storage import ConfigKind
from pcvs.helpers.storage import ConfigScope

from ..conftest import dummy_fs_with_configlocator_patch
from ..conftest import isolated_fs


def test_scope():
    """Test ConfigScope class."""
    assert ConfigScope.fromstr("not a scope") is None
    for scope in ConfigScope:
        scope_str = str(scope)
        assert scope_str is not None
        assert ConfigScope.fromstr(scope_str) is not None
        assert scope in ConfigScope.all_scopes()


def test_kind():
    """Test ConfigKind class."""
    assert ConfigKind.fromstr("not a kind") is None
    for kind in ConfigKind:
        kind_str = str(kind)
        assert kind_str is not None
        assert ConfigKind.fromstr(kind_str) is not None
        assert kind in ConfigKind.all_kinds()
        if kind != ConfigKind.PLUGIN:
            assert ConfigKind.get_file_exts(kind) == [".yml", ".yaml"]
        else:
            assert ConfigKind.get_file_exts(kind) == [".py"]


def test_desc():
    """Test ConfigDesc class."""
    with isolated_fs() as tmp:
        test = ConfigDesc(
            "name",
            Path(os.path.join(tmp, ".pcvs", "profile", "default.yml")),
            ConfigKind.PROFILE,
            ConfigScope.LOCAL,
        )
        assert test.full_name == f"{ConfigScope.LOCAL}:{ConfigKind.PROFILE}:name"
        assert not test.exist
        test.path.parent.mkdir(parents=True)
        test.path.touch()
        assert test.exist


def test_locator() -> None:
    """Test ConfigLocator class."""
    with dummy_fs_with_configlocator_patch() as (cl, scopes_to_paths):
        # extension
        assert cl.check_filename_exts(Path("test.yml"), ConfigKind.PROFILE) == [Path("test.yml")]
        assert cl.check_filename_exts(Path("test"), ConfigKind.PROFILE) == [
            Path("test.yml"),
            Path("test.yaml"),
        ]
        assert cl.check_filename_exts(Path("test.py"), ConfigKind.PLUGIN) == [Path("test.py")]
        assert cl.check_filename_exts(Path("test"), ConfigKind.PLUGIN) == [Path("test.py")]

        # scope and kind
        # # 1 token
        assert cl.parse_scope_and_kind("local") == (ConfigScope.LOCAL, None)
        assert cl.parse_scope_and_kind("profile") == (None, ConfigKind.PROFILE)
        assert cl.parse_scope_and_kind("local", ConfigKind.PROFILE) == (
            ConfigScope.LOCAL,
            ConfigKind.PROFILE,
        )
        assert isinstance(cl.parse_scope_and_kind("gibrish"), str)
        assert isinstance(cl.parse_scope_and_kind("profile", ConfigKind.PLUGIN), str)
        # # 2 tokens
        assert cl.parse_scope_and_kind("local:profile") == (ConfigScope.LOCAL, ConfigKind.PROFILE)
        assert cl.parse_scope_and_kind("local:profile", ConfigKind.PROFILE) == (
            ConfigScope.LOCAL,
            ConfigKind.PROFILE,
        )
        assert isinstance(cl.parse_scope_and_kind("gibrish:profile"), str)
        assert isinstance(cl.parse_scope_and_kind("local:gibrish"), str)
        assert isinstance(cl.parse_scope_and_kind("local:profile", ConfigKind.PLUGIN), str)

        # get_storage_dir
        assert cl.get_storage_dir(ConfigScope.LOCAL) == Path(scopes_to_paths[ConfigScope.LOCAL])
        assert cl.get_storage_dir(ConfigScope.LOCAL, ConfigKind.PROFILE) == Path(
            scopes_to_paths[ConfigScope.LOCAL]
        ).joinpath("profile")

        # get_storage_path
        assert cl.get_storage_path(
            Path("default.yml"), ConfigKind.PROFILE, ConfigScope.LOCAL
        ) == Path(scopes_to_paths[ConfigScope.LOCAL]).joinpath("profile").joinpath("default.yml")

        # default local profile ConfigDesc
        default_lp = ConfigDesc(
            "default",
            Path(scopes_to_paths[ConfigScope.LOCAL]).joinpath("profile/default.yml"),
            ConfigKind.PROFILE,
            ConfigScope.LOCAL,
        )
        test_lp = ConfigDesc(
            "test",
            Path(scopes_to_paths[ConfigScope.LOCAL]).joinpath("profile/test.yml"),
            ConfigKind.PROFILE,
            ConfigScope.LOCAL,
        )

        # find_config
        assert cl.find_config(Path("default"), ConfigKind.PROFILE) == default_lp
        assert cl.find_config(Path("default.yml"), ConfigKind.PROFILE) == default_lp
        assert cl.find_config(Path("default"), ConfigKind.PROFILE, ConfigScope.LOCAL) == default_lp
        assert cl.find_config(Path("test"), ConfigKind.PROFILE) is None

        # parse_full
        # # 1 token
        # kind is passed as parameter and file exist so we can guess scope.
        assert cl.parse_full("default", ConfigKind.PROFILE, True) == default_lp
        # kind is passed as parameter but file may not exist -> FAIL
        assert isinstance(cl.parse_full("default", ConfigKind.PROFILE, None), str)
        # kind is passed as parameter but file does not exist -> FAIL
        assert isinstance(cl.parse_full("default", ConfigKind.PROFILE, False), str)
        # kind is missing (not parameter nor token)
        assert isinstance(cl.parse_full("default", None, True), str)
        # # 2 token
        # no scope provided on a conf that may/does not exist.
        assert isinstance(cl.parse_full("profile:default", None, None), str)
        assert isinstance(cl.parse_full("profile:default", None, False), str)
        # no kind specify
        assert isinstance(cl.parse_full("local:default", None, None), str)
        # wrong number of args
        assert isinstance(cl.parse_full("test:local:profile:default", None, None), str)
        # does not exist but should
        assert isinstance(cl.parse_full("local:profile:test", None, True), str)
        # should exist and does
        assert cl.parse_full("local:profile:default", None, True) == default_lp
        # may exist and does
        assert cl.parse_full("local:profile:default", None, None) == default_lp
        # may exist and does not
        assert cl.parse_full("local:profile:test", None, None) == test_lp
        # should not exist and does
        assert isinstance(cl.parse_full("local:profile:default", None, False), str)
        # should not exist and does no
        assert cl.parse_full("local:profile:test", None, False) == test_lp

        # list_configs
        assert cl.list_configs(ConfigKind.PROFILE, ConfigScope.LOCAL) == [default_lp]
        assert len(cl.list_configs(ConfigKind.PROFILE)) == 3

        # list_all_configs
        assert len(cl.list_all_configs(ConfigScope.LOCAL)) == len(ConfigKind.all_kinds())
        assert len(cl.list_all_configs()) == len(ConfigKind.all_kinds()) * 3
