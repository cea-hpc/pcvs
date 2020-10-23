import os
from pcvsrt.helpers.log import utf
import base64
import jsonschema
import tempfile
import subprocess
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
                    err_msg = base64.b64encode(str(e.message).encode('utf-8'))
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
                err_msg = base64.b64encode(str(e.message).encode('utf-8'))
                errors.setdefault(err_msg, 0)
                errors[err_msg] += 1
                log.debug(str(e))
                
            t.add_row([token, obj.full_name])
    print(t)
    return errors

def process_check_setup_file(filename, prefix):
    err_msg = None
    token = utf('fail')
    data = None
    env = os.environ
    env.update(pvRun.build_env_from_configuration({}))
    try:
        tdir = tempfile.mkdtemp()
        with io.cwd(tdir):
            env['pcvs_src'] = os.path.dirname(filename).replace(prefix, '')
            env['pcvs_testbuild'] = tdir
            if not os.path.isdir(os.path.join(tdir, prefix)):
                os.makedirs(os.path.join(tdir, prefix))
            proc = subprocess.Popen([filename, prefix], env=env, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            fds = proc.communicate()
            if fds[1]:
                err_msg = base64.b64encode(fds[1])
            else:
                data = fds[0].decode('utf-8')
                token = log.utf('succ')
    except subprocess.CalledProcessError as e:
        err_msg = base64.b64encode(str(e.stderr).encode('utf-8'))
        
    return (err_msg, token, data)

scheme = validation.ValidationScheme('te')
def process_check_yaml_stream(data):
    global scheme
    token_load = token_yaml = "{}".format(utf('fail'))
    err_msg = None
    try:
        stream = yaml.load(data, Loader=yaml.FullLoader)
        token_load = "{}".format(utf('succ'))

        scheme.validate(stream, fail_on_error=False)
        token_yaml = "{}".format(utf('succ'))
        
    except yaml.YAMLError as e:
        err_msg = base64.b64encode(str(e).encode('utf-8'))
    except jsonschema.exceptions.ValidationError as e:
        err_msg = base64.b64encode(str(e.message).encode('utf-8'))

    
    return (err_msg, token_load, token_yaml)

def process_check_directory(dir):
    errors = dict()
    setup_files, yaml_files = pvRun.find_files_to_process({os.path.basename(dir): dir})

    if setup_files:
        log.print_section('Analyzing scripts: (script{s}YAML{s}valid)'.format(s=log.utf('sep_v')))
        for _, subprefix, f in setup_files:
            token_script = token_load = token_yaml = log.utf('fail')
            err, token_script, data = process_check_setup_file(os.path.join(dir, subprefix, f), subprefix)
            if err:
                errors.setdefault(err, 0)
                errors[err] += 1
            else:
                err, token_load, token_yaml = process_check_yaml_stream(data)
                
                if err:
                    errors.setdefault(err, 0)
                    errors[err] += 1
            log.print_item(' {}{}{}{}{} {}'.format(
                token_script,
                log.utf('sep_v'),
                token_load,
                log.utf('sep_v'),
                token_yaml,
                os.path.join(dir, subprefix)
                ), with_bullet=False)

            if err:
                log.info("FAILED: {}".format(base64.b64decode(err).decode('utf-8')))

    if yaml_files:
        log.print_section("Analysis: pcvs.yml* (YAML{}Valid)".format(log.utf('sep_v')))
        for _, subprefix, f in yaml_files:
            with open(os.path.join(dir, subprefix, f), 'r') as fh:     
                err, token_load, token_yaml = process_check_yaml_stream(fh.read())
                if err:
                    errors.setdefault(err, 0)
                    errors[err] += 1

            log.print_item(' {}{}{} {}'.format(
                token_load,
                log.utf('sep_v'),
                token_yaml,
                os.path.join(dir, subprefix)), with_bullet=False)
            
            if err:
                log.info("FAILED: {}".format(base64.b64decode(err).decode('utf-8')))
    return errors
