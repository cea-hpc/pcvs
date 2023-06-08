import os

import click

NAME_BUILDIR = ".pcvs-build"
NAME_BUILDFILE = ".pcvs-isbuilddir"
NAME_SRCDIR = ".pcvs"
NAME_RUN_CONFIG_FILE = ".pcvs-config.yml"
NAME_BUILD_CONF_FN = "conf.yml"
NAME_BUILD_CONF_SH = "conf.env"
NAME_BUILD_RESDIR = "rawdata"
NAME_BUILD_SCRATCH = "test_suite"
NAME_BUILD_ARCHIVE_DIR = "old_archives"
NAME_BUILD_CACHEDIR = "cache"
NAME_BUILD_CONTEXTDIR = os.path.join(NAME_BUILD_CACHEDIR, "runner_ctx")

NAME_DEBUG_FILE = "pcvs-debug.log"
NAME_LOG_FILE = "pcvs-out.log"

PATH_INSTDIR = os.path.dirname(__file__)
PATH_HOMEDIR = click.get_app_dir('pcvs', force_posix=True)
PATH_SESSION = os.path.join(PATH_HOMEDIR, "session.yml")
PATH_BANK = os.path.join(PATH_HOMEDIR, "bank.yml")
PATH_VALCFG = os.path.join(PATH_HOMEDIR, "validation.yml")

