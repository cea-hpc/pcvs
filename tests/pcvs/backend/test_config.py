import os
from pathlib import Path

from pcvs.helpers.storage import ConfigKind
from pcvs.helpers.storage import ConfigScope

from ..conftest import dummy_fs_with_configlocator_patch


def test_config_scopes():
    """Check that config are correctly found at the right scope."""
    with dummy_fs_with_configlocator_patch() as (cl, scopes_to_paths):
        for k in ConfigKind.all_kinds():
            for s in ConfigScope.all_scopes():
                confs = cl.list_configs(k, s)
                print(f"test: {str(k)}, {str(s)}")
                assert len(confs) == 1
                assert confs[0].path == Path(
                    os.path.join(
                        scopes_to_paths[s],
                        str(k).lower(),
                        f"default{ConfigKind.get_file_exts(k)[0]}",
                    )
                )
