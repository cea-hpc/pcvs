import jsonschema
from ruamel.yaml import YAML, YAMLError
import os
import sys

if __name__ == '__main__':
    ret = 0
    template_dir = os.path.join(os.path.dirname(__file__), "..", "pcvs", "templates")
    scheme_dir = os.path.join(os.path.dirname(__file__), "..", "pcvs", "schemes")
    
    list_of_templates = os.listdir(template_dir)
    list_of_schemes = os.listdir(scheme_dir)
    verbose = ("-v" in sys.argv)
    
    for t in list_of_templates:
        # ignore compatibility files
        if "-compat.yml" in t:
            continue
        scheme_name = t
        err = None
        
        # look for YAML schemes either if format is in yaml or json
        scheme_name = scheme_name.replace("-format.json", "-scheme.yml")
        scheme_name = scheme_name.replace("-format.yml", "-scheme.yml")
        scheme_yaml = {}
        template_yaml = {}
        
        # if the scheme is found for this templates
        if scheme_name in list_of_schemes:
            try:
                # load both
                with open(os.path.join(scheme_dir, scheme_name), 'r') as fh:
                    scheme_yaml = YAML(typ='safe').load(fh)
                with open(os.path.join(template_dir, t), 'r') as fh:
                    template_yaml = YAML(typ='safe').load(fh)
                
                # ... and validate
                jsonschema.validate(template_yaml, scheme_yaml)
                state = "OK"
                
            # error while loading YAML (either one)
            except YAMLError as e:
                state = "NOK (YAML)"
                err = e
                
            # error in template format
            except jsonschema.ValidationError as e:
                state = "NOK (FORMAT)"
                ret = 1
                err = e.message

            except jsonschema.SchemaError as e:
                state = "NOK (SCHEME)"
                ret = 1
                err = e.message
        # no scheme exist (normal ?)
        else:
            state = "NOK (NFOUND)"
            ret = 1
        
        # display status
        print("* {:12}: {} -> {}".format(state, t, scheme_name))
        if err and verbose:
            print("\t-> {}".format(err))

# exit non-zero if at least one error is raised
sys.exit(ret)
    