import yaml
import os
from pcvsrt.utils import logs
from pcvsrt import config


PREFIXPATH = ".."
BASEPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), PREFIXPATH))

class Profile:

    @staticmethod
    def check_config_labels(config_labels):
        return config_labels in config.CONFIG_BLOCKS
    
    def __init__(self):
        self.blocks = {block_name: None for block_name in config.CONFIG_BLOCKS}

    def populate(self): pass

    def load(self, name):
        yaml = {}
        
        return yaml

    def save(self, name): pass
    
