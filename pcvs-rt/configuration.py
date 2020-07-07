import yaml
import os


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
            print("Unable to open file %s" % filepath)
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

    def dumpToDisk(self):
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
    test = Configuration()
    test.loadRuntime("../build_scripts/configuration/runtimes/mpc.yml")
    test.loadCompiler("../build_scripts/configuration/compilers/mpc.yml")
    test.loadEnv("../build_scripts/configuration/environment/inti.yml")

    for i, j in test.getConfig().items():
        print(i, j)
