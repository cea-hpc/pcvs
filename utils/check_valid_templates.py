import os
import sys

import jsonschema
from ruamel.yaml import YAML, YAMLError

if __name__ == '__main__':
    ret = 0
    template_dir = os.path.join(os.path.dirname(__file__), "..", "pcvs", "templates")
    scheme_dir = os.path.join(os.path.dirname(__file__), "..", "pcvs", "schemes")
    
    list_of_templates = list()
    for s in ['config', 'profile']:
        d = os.path.join(template_dir, s)
        for f in os.listdir(d):
            list_of_templates.append(os.path.join(d, f))

    list_of_schemes = os.listdir(scheme_dir)
    verbose = ("-v" in sys.argv)
    
    for t in list_of_templates:
        with open(os.path.join(t), 'r') as fh:
            template_yaml = YAML(typ='safe').load(fh)
            err = None
            state = "NOK"
            for s in list_of_schemes:
        
                scheme_yaml = {}
                template_yaml = {}
                try:
                    with open(os.path.join(scheme_dir, s), 'r') as fh:
                        scheme_yaml = YAML(typ='safe').load(fh)
                    
                    # ... and validate
                    jsonschema.validate(template_yaml, scheme_yaml)
                    state = "OK"
                    break
                    
                # error while loading YAML (either one)
                except (YAMLError, jsonschema.ValidationError, jsonschema.SchemaError) as e:
                    state = "NOK"
                    err = e
                    
                # display status
            print("* {:12}: {}".format(state, t))
            if err and verbose:
                print("\t-> {}".format(err))

# exit non-zero if at least one error is raised
sys.exit(ret)
    
