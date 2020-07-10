import yaml
import os
import utils

PCVS_HOME = os.path.join(os.path.dirname(__file__), "../test")
PCVS_CONFIG_PATH = os.path.abspath(os.path.join(PCVS_HOME, "saves"))


def retrieve_list_of(domain):
    # prune '.yml' -> 4 characters
    return [filename[:-4] for filename in os.listdir(os.path.join(PCVS_CONFIG_PATH, domain))]

class Configuration:

    def __init__(self, buildpath="."):
        self.__config = dict()
        self.__config['buildpath'] = buildpath
        self.__runtime_filepath = None
        self.__compiler_filepath = None
        self.__env_filepath = None

    def __load_yaml_file(self, filepath):
        try:
            file = open(filepath, 'r')
            content = yaml.load(file, Loader=yaml.Loader)
        except IOError:
            utils.err("Unable to open file %s" % filepath)
        except yaml.scanner.ScannerError:
            print("Badly formatted file: %s" % filepath)
        else:
            return content

    def loadRuntime(self, filepath):
        self.runtime_filepath = filepath
        self.__config['runtime'] = self.__load_yaml_file(filepath)

    def loadCompiler(self, filepath):
        self.compiler_filepath = filepath
        self.__config['compiler'] = self.__load_yaml_file(filepath)

    def loadEnv(self, filepath):
        self.env_filepath = filepath
        self.__config['env'] = self.__load_yaml_file(filepath)

    def flushToDisk(self):
        filepath = self.__config['buildpath']
        try:
            file = open(filepath, 'w')
            yaml.dump(self.__config, file, Dumper=yaml.Dumper)
        except IOError:
            
            pass
        else:
            pass

    def getConfig(self):
        return self.__config


if __name__ == '__main__':
    
    print(retrieve_list_of("compilers"))
