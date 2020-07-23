import os
import subprocess
import yaml
import shutil
import tarfile
import glob
from tqdm import tqdm

import pkg_resources
import pcvsrt
from pcvsrt.utils import logs, files
from pcvsrt import config, profile, descriptor

run_settings = {}
list_of_tes = {}

def __print_summary():
    global run_settings
    logs.print_section("Validation details:")
    logs.print_item("Build into: {}".format(run_settings['output']))
    logs.print_item("Verbosity level: {}".format(run_settings['verbose']))
    logs.print_item("Profile: '{}'".format(run_settings['pfname']))
    logs.print_item("Paths:")
    for k, v in run_settings['user_input'].items():
        logs.print_item("{}: {}".format(k, v), depth=2)
    # logs.print_item(": {}".format())


def __build_jchronoss():
    archive_name = None
    archive_prefix = os.path.join(run_settings['output'], "cache/jchrns")
    # FIXME: Dirty way to locate the archive
    for f in glob.glob(os.path.join(pcvsrt.ROOTPATH, "../**/jchronoss-*"), recursive=True):
        if 'jchronoss-' in f:
            archive_name = os.path.join(pcvsrt.ROOTPATH, f)
            break
    assert(archive_name)
    tarfile.open(os.path.join(archive_name)).extractall(archive_prefix)
    jchronoss_root = glob.glob(os.path.join(archive_prefix, "*/CMakeLists.txt"))
    assert (jchronoss_root)
    with files.cwd(os.path.join(archive_prefix, "build")):
        command = "cmake {} -DCMAKE_INSTALL_PREFIX={} -DENABLE_COLOR={} && make install".format(
            os.path.dirname(jchronoss_root[0]),
            os.path.join(archive_prefix, "install"),
            "ON" if run_settings['color'] else "OFF"
        )
        res = subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def __setup_webview():
    pass

def __build_third_party():
    logs.print_section("Build third-party tools")

    logs.print_item("job orchestrator (JCHRONOSS)")
    __build_jchronoss()

    logs.print_item("Web-based reporting tool")
    __setup_webview()

def prepare(settings):
    global run_settings

    logs.print_section("Prepare environment")
    run_settings = settings

    logs.print_item("Check valid output directory")
    test_output_dir = os.path.join(run_settings['output'], "test_suite")
    if os.path.isdir(test_output_dir):
        if not run_settings['override']:
            logs.err("Previous run artifacts found in {}. Please use '--override' to ignore.".format(settings['output']), abort=1)
        else:
            shutil.rmtree(test_output_dir)
    os.mkdir(test_output_dir)

    logs.print_item("Load Profile {}".format(settings['pfname']))
    pf = pcvsrt.profile.Profile()
    run_settings['profile'] = pf.load(settings['pfname'])
    
    logs.print_item("Save current configuration")
    output_dir = settings['output']
    with open(os.path.join(output_dir, "conf.yml"), 'w') as config_settings:
        yaml_file = yaml.safe_dump(run_settings, config_settings)

    __build_third_party()


def __substitute_yaml_tag(dict_to_parse):
    pass


def load_benchmarks(test_dict):
    global run_settings
    global list_of_tes

    logs.print_section("Load Benchmarks")
    environ = {}

    run_settings['user_input'] = test_dict
    to_process = []
    # discovery and processing split to add a progress bar (determinist)
    for label, path in test_dict.items():
        for root, dirs, files in os.walk(path):
            if '.pcvsrt' in root or 'build_scripts' in root: # ignore pcvs-rt conf subdirs
                continue
           
            to_process += [(path, root, f) for f in files if 'pcvs.setup' in f or 'pcvs.yml' in f]

    for path, root, f in tqdm(to_process):
        environ['pcvs_src'] = path
        environ['pcvs_build'] = run_settings['output']
        filepath = os.path.join(root, f)
        te_package = root.replace(path, '').replace('/', ".")
        fileroot = {}
        print(f)
        if f == 'pcvs.setup':
            print(f)
            res = subprocess.run(["echo", filepath, te_package], env=environ, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
            print(res.stdout.decode("utf-8"))
            try: pass
                #fileroot = yaml.safe_load(res.stdout.decode('utf-8'))
            except yaml.YAMLError as e:
                logs.err("Bad YAML format:\n{}".format(e), abort=1)
        elif 'pcvs.yml' in f:
            try: pass
                #fileroot = yaml.safe_load(open(filepath, 'r'))
            except yaml.YAMLError as e:
                logs.err("Bad YAML format:\n{}".format(e), abort=1)
            if f.endswith('pcvs.yml.in'):
                __substitute_yaml_tag(fileroot)
                # apply replacement
                pass
        else:  # Not a pcvs-related file
            continue

        for blockname, blockdesc in fileroot.items():
            te_name = label + te_package + "." + blockname
            list_of_tes[te_name] = descriptor.TEDescriptor(fileroot)
        print(list_of_tes)
        logs.err("STOP")


def run():
    __print_summary()
    logs.print_section("Start JCHRONOSS")
    pass


def terminate():
    logs.print_section("Build final archive")
    if shutil.which("xsltproc") is not None:
        logs.print_section("Build browsable results")


    pass