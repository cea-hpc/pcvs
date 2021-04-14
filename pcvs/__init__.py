import os

NAME_BUILDIR = ".pcvs-build"
NAME_BUILDFILE = ".pcvs-isbuilddir"
NAME_SRCDIR = ".pcvs"

PATH_INSTDIR = os.path.dirname(__file__)
PATH_HOMEDIR = os.path.join(os.environ['HOME'], NAME_SRCDIR)
PATH_SESSION = os.path.join(PATH_HOMEDIR, "session.yml")
PATH_SESSION_LOCKFILE = os.path.join(PATH_HOMEDIR, "session.yml.lck")
PATH_VALCFG = os.path.join(PATH_HOMEDIR, "validation.yml")
