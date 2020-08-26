from addict import Dict


class Settings(Dict):
    def __setitem__(self, param, value):
        if isinstance(value, dict):
            value = Dict(value)
        Dict.__setitem__(self, param, value)

    def serialize(self):
        return self.to_dict()


sysTable = Settings()
