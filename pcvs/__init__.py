import os

import click

NAME_BUILDIR = ".pcvs-build"
NAME_BUILDFILE = ".pcvs-isbuilddir"
NAME_BUILDIR_LOCKFILE = ".pcvs-wip"
NAME_SRCDIR = ".pcvs"
NAME_BUILD_CONF_FN = "conf.yml"
NAME_BUILD_RESDIR = "rawdata"

PATH_INSTDIR = os.path.dirname(__file__)
PATH_HOMEDIR = click.get_app_dir('pcvs', force_posix=True)
PATH_SESSION = os.path.join(PATH_HOMEDIR, "session.yml")
PATH_SESSION_LOCKFILE = os.path.join(PATH_HOMEDIR, "session.yml.lck")
PATH_VALCFG = os.path.join(PATH_HOMEDIR, "validation.yml")

def create_home_dir():
    if not os.path.exists(PATH_HOMEDIR):
        os.makedirs(PATH_HOMEDIR)

