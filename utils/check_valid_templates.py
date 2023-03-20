import os
import sys

import jsonschema
from ruamel.yaml import YAML, YAMLError

from pcvs.backend.config import ConfigurationBlock, init as cinit
from pcvs.backend.profile import Profile, init as pinit
from pcvs.helpers.exceptions import ValidationException

verbose = ("-v" in sys.argv)

def manage_validation(label, f):
    err = None
    try:
        f()
        state = "OK"
    except (ValidationException.FormatError, ValidationException.SchemeError) as e:
        state = "NOK"
        err = e.dbg
    print("* {:12}: {}".format(state, label))
    if err and verbose:
        print("\t-> {}".format(err))
        

if __name__ == '__main__':
    template_dir = os.path.join(os.path.dirname(__file__), "..", "pcvs", "templates")
    cinit()
    for config in os.listdir(os.path.join(template_dir, "config")):
        conf_kind = config.split(".")[0]
        t = ConfigurationBlock(conf_kind, "test", "local")
        with open(os.path.join(template_dir, "config", config), 'r') as fh:
            data = YAML(typ='safe').load(fh)
            t.fill(data)
        manage_validation(config, t.check)
     
    pinit()    
    for profile in os.listdir(os.path.join(template_dir, "profile")):
        t = Profile("tmp", "local")
        with open(os.path.join(template_dir, "profile", profile), 'r') as fh:
            data = YAML(typ='safe').load(fh)
            t.fill(data)
        manage_validation(profile, t.check)
