from os import path
from pcvsrt import config, profile


ROOTPATH = path.abspath(path.join(path.dirname(__file__)))

config.init()
profile.init()
