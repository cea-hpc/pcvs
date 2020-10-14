import os
from pcvsrt.helpers.log import utf
import base64
import jsonschema
from pcvsrt.helpers import validation
import yaml
import pprint
from prettytable import PrettyTable


from pcvsrt.cli.run import commands as cmdRun
from pcvsrt.cli.config import commands as cmdConfig
from pcvsrt.cli.config import backend as pvConfig
from pcvsrt.cli.profile import commands as cmdProfile
from pcvsrt.cli.profile import backend as pvProfile

from pcvsrt.helpers import io, log
from pcvsrt.cli.run import backend as pvRun


def retrieve_all_test_scripts(output=None):
    if output is None:
        output = "./.pcvs/test_suite"
    l = list()
    for root, _, files in os.walk(output):
        for f in files:
            if f == 'list_of_tests.sh':
                l.append(os.path.join(root, f))
    return l


def retrieve_test_script(testname, output=None):
    if output is None:
        output = "./.pcvs/test_suite"
    # first one is directory name
    # last one is test name
    prefix = os.path.dirname(testname)
    return os.path.join(
        output,
        prefix,
        "list_of_tests.sh"
    )

def process_check_configs():
    errors = dict()
    t = PrettyTable()
    t.field_names = ["Valid", "ID"]
    t.align['ID'] = "l"

    for kind in pvConfig.CONFIG_BLOCKS:
        for scope in io.storage_order():
            for blob in pvConfig.list_blocks(kind, scope):
                token = log.utf('fail')
                err_msg = ""
                obj = pvConfig.ConfigurationBlock(kind, blob[0], scope)
                obj.load_from_disk()

                try:
                    obj.check(fail=False)
                    token = log.utf('succ')
                except jsonschema.exceptions.ValidationError as e:
                    err_msg = base64.b64encode(str(e.message).encode('ascii'))
                    errors.setdefault(err_msg, 0)
                    errors[err_msg] += 1
                    log.debug(str(e))
                
                t.add_row([token, obj.full_name])
    print(t)
    return errors

def process_check_profiles():
    t = PrettyTable()
    errors = dict()
    t.field_names = ["Valid", "ID"]
    t.align['ID'] = "l"
    
    for scope in io.storage_order():
        for blob in pvProfile.list_profiles(scope):
            token = log.utf('fail')
            obj = pvProfile.Profile(blob[0], scope)
            obj.load_from_disk()
            try:
                obj.check(fail=False)
                token = log.utf('succ')
            except jsonschema.exceptions.ValidationError as e:
                err_msg = base64.b64encode(str(e.message).encode('ascii'))
                errors.setdefault(err_msg, 0)
                errors[err_msg] += 1
                log.debug(str(e))
                
            t.add_row([token, obj.full_name])
    print(t)
    return errors

def process_check_directory(dir):
    errors = dict()
    scheme = validation.ValidationScheme('te')
    setup_files, yaml_files = pvRun.find_files_to_process({os.path.basename(dir): dir})

    if setup_files:
        log.print_section('Analyzing scripts: (run{}yaml)'.format(log.utf('sep_v')))
        for _, subprefix, f in setup_files:

            token_script = log.utf("fail")
            token_yaml = log.utf("fail")

            h = base64.b64encode("Not implemented yet!".encode('ascii'))
            errors.setdefault(h, 0)
            errors[h] += 2

            log.print_item(' {}{}{} {}'.format(
                token_script,
                log.utf('sep_v'),
                token_yaml,
                subprefix
                ), with_bullet=False)
   
    if yaml_files:
        log.print_section("Analysis: pcvs.yml* (load{}yaml)".format(log.utf('sep_v')))
        for _, subprefix, f in yaml_files:
            token_load = token_yaml = "{}".format(utf('fail'))
            with open(os.path.join(dir, subprefix, f), 'r') as fh:
                try:
                    stream = yaml.load(fh, Loader=yaml.FullLoader)
                    token_load = "{}".format(utf('succ'))
            
                    scheme.validate(stream, fail_on_error=False)
                    token_yaml = "{}".format(utf('succ'))
                    
                except yaml.YAMLError as e:
                    err_msg = base64.b64encode(str(e).encode('ascii'))
                    errors.setdefault(err_msg, 0)
                    errors[err_msg] += 1
                except jsonschema.exceptions.ValidationError as e:
                    err_msg = base64.b64encode(str(e.message).encode('ascii'))
                    errors.setdefault(err_msg, 0)
                    errors[err_msg] += 1
                
                log.print_item(' {}{}{} {}'.format(
                    token_load,
                    log.utf('sep_v'),
                    token_yaml,
                    subprefix), with_bullet=False)
    return errors
