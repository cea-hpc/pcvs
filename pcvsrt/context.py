from addict import Dict
import pprint

class Settings(Dict):
    def __setitem__(self, param, value):
        if isinstance(value, dict):
            value = Dict(value)
        Dict.__setitem__(self, param, value)


settings = Settings()


def serialize():
    return settings.to_dict()
