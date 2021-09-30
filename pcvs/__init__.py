import os

import click

NAME_BUILDIR = ".pcvs-build"
NAME_BUILDFILE = ".pcvs-isbuilddir"
NAME_SRCDIR = ".pcvs"
NAME_BUILD_CONF_FN = "conf.yml"
NAME_BUILD_RESDIR = "rawdata"

PATH_INSTDIR = os.path.dirname(__file__)
PATH_HOMEDIR = click.get_app_dir('pcvs', force_posix=True)
PATH_SESSION = os.path.join(PATH_HOMEDIR, "session.yml")
PATH_BANK = os.path.join(PATH_HOMEDIR, "bank.yml")
PATH_VALCFG = os.path.join(PATH_HOMEDIR, "validation.yml")
