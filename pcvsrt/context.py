from addict import Dict
import pprint

class Settings(Dict):
    def __setitem__(self, param, value):
        if isinstance(value, dict):
            value = Dict(value)
        Dict.__setitem__(self, param, value)


settings = Settings()

def get_or_none(k, dflt=None):
    if k in settings:
        return settings[k]
    else:
        return dflt

def serialize():
    return settings.to_dict()
