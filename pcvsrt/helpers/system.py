from addict import Dict


class Settings(Dict):
    def __setitem__(self, param, value):
        if isinstance(value, dict):
            value = Dict(value)
        Dict.__setitem__(self, param, value)

    def serialize(self):
        return self.to_dict()


class CfgCompiler:
    def __init__(self, node):
        pass


class CfgRuntime:
    def __init__(self, node):
        pass


class CfgMachine:
    def __init__(self, node):
        pass


class CfgCriterion:
    def __init__(self, node):
        pass


class CfgTemplate:
    def __init__(self, node):
        pass


class CfgValidation:
    def __init__(self, node):
        pass


sysTable = Settings()

def init_configuration(profile):
    pass
