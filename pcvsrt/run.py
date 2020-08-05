import os
import subprocess
import yaml
import shutil
import tarfile
import glob
import pprint
import pcvsrt
from pcvsrt import config, profile, descriptor, globals, logs, files

run_settings = {}
list_of_tes = {}


def __print_summary():
    global run_settings
    logs.print_section("Validation details:")
    logs.print_item("Build into: {}".format(run_settings['validation']['output']))
    logs.print_item("Verbosity level: {}".format(run_settings['validation']['verbose']))
    logs.print_item("Profile: '{}'".format(run_settings['validation']['pfname']))
    logs.print_item("Paths:")
    for k, v in run_settings['user_dirs'].items():
        logs.print_item("{}: {}".format(k, v), depth=2)
    # logs.print_item(": {}".format())


def __build_jchronoss():
    archive_name = None
    archive_prefix = os.path.join(run_settings['validation']['output'], "cache/jchrns")
    # FIXME: Dirty way to locate the archive
    for f in glob.glob(os.path.join(globals.ROOTPATH, "../**/jchronoss-*"), recursive=True):
        if 'jchronoss-' in f:
            archive_name = os.path.join(globals.ROOTPATH, f)
            break
    assert(archive_name)
    tarfile.open(os.path.join(archive_name)).extractall(archive_prefix)
    jchronoss_root = glob.glob(os.path.join(archive_prefix, "*/CMakeLists.txt"))
    assert (jchronoss_root)
    with files.cwd(os.path.join(archive_prefix, "build")):
        command = "cmake {} -DCMAKE_INSTALL_PREFIX={} -DENABLE_COLOR={} && make install".format(
            os.path.dirname(jchronoss_root[0]),
            os.path.join(archive_prefix, "install"),
            "ON" if run_settings['validation']['color'] else "OFF"
        )
        res = subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def __setup_webview():
    pass

def __build_tools():
    logs.print_section("Build third-party tools")

    logs.print_item("job orchestrator (JCHRONOSS)")
    __build_jchronoss()

    logs.print_item("Web-based reporting tool")
    __setup_webview()


def prepare(settings, dirs_dict):
    global run_settings

    logs.print_section("Prepare environment")
    run_settings['validation'] = settings
    run_settings['user_dirs'] = dirs_dict

    logs.print_item("Check valid output directory")
    test_output_dir = os.path.join(run_settings['validation']['output'], "test_suite")
    if os.path.isdir(test_output_dir):
        if not run_settings['validation']['override']:
            logs.err("Previous run artifacts found in {}. Please use '--override' to ignore.".format(settings['output']), abort=1)
        else:
            shutil.rmtree(test_output_dir)
    
    for label in dirs_dict.keys():
        os.makedirs(os.path.join(test_output_dir, label))
    
    logs.print_item("Load Profile '{}'".format(settings['pfname']))
    (scope, label) = pcvsrt.profile.extract_profile_from_token(settings['pfname'])
    pf = pcvsrt.profile.Profile(label, scope)
    run_settings['profile'] = pf.dump()
    
    logs.print_item("Save current configuration")
    output_dir = run_settings['validation']['output']
    with open(os.path.join(output_dir, "conf.yml"), 'w') as config_settings:
        yaml_file = yaml.safe_dump(run_settings, config_settings)

    __build_tools()


tokens = {
    '@BUILDPATH@': None,
    '@SRCPATH@': None,
    '@SPACKPATH@': "TBD",
    '@HOME@': os.environ['HOME'],
    '@USER@': os.environ['USER']
}

def __substitute_pcvs_token(string, src, build):
    for t, tv in tokens.items():
        if 'BUILDPATH' in t:
            tv = build
        elif 'SRCPATH' in t:
            tv = src
        string.replace(t, tv)


def __replace_tokens(obj, src, build):
    if isinstance(obj, str):
        return __substitute_pcvs_token(obj, src, build)
    elif isinstance(obj, list) or isinstance(obj, set):
        return [__substitute_pcvs_token(elt, src, build) for elt in obj]
    elif isinstance(obj, dict):
        for k, v in obj.items():
            obj[k] = __replace_tokens(v, src, build)
        return obj


# will convert the 
def __load_yaml_legacy_syntax(f):
    # barely legal to do that..;
    old_group_file = os.path.join(os.path.dirname(__file__), "templates/group-compat.yml")
    cmd = "pcvs_convert {} --stdout -k te -t {} 2>/dev/null".format(f, old_group_file)
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        if res.returncode != 0:
            logs.err("Failed to convert {}".format(f), abort=1)
        ret = yaml.load(res.stdout.decode('utf-8'), Loader=yaml.FullLoader)
    except yaml.YAMLError as e:
        logs.err("Bad YAML", "{}".format(e), abort=1)
    except Exception as e:
        logs.err("Yolo: {}".format(e), abort=1)
    return ret


def __load_yaml_to_tree(f):
    try:
        with open(f, 'r') as fh:
            obj = yaml.load(fh, Loader=yaml.FullLoader)

        # TODO: Validate input & raise YAMLError if invalid

    except yaml.YAMLError:
        logs.warn("Issue while loading {}".format(f),
                  "Attempt to use legacy syntax")
        obj = __load_yaml_legacy_syntax(f)
    except Exception:
        logs.err("Err loading the YAML file {}".format(src), abort=1)
        
    return obj

def load_benchmarks():
    global run_settings
    global list_of_tes

    logs.print_section("Load Benchmarks")
    environ = {}

    path_dict = run_settings['user_dirs']
    setup_files = list()
    yaml_files = list()
    final = list()

    logs.info("Processing user directories: {}".format(pprint.pformat(path_dict)))
    # discovery may take a while with some systems
    logs.print_item("PCVS-related file detection")
    # iterate over user directories
    for label, path in path_dict.items():
        # for each, walk through the tree
        for root, _, list_files in os.walk(path):
            last_dir = os.path.basename(root)
            # if the current dir is a 'special' one, discard
            if last_dir in ['.pcvsrt', '.pcvs', "build_scripts"]:
                continue
            # otherwise, save the file
            for f in list_files:
                # [1:] to remove extra '/'
                if 'pcvs.setup' == f:
                    setup_files.append((label, root.replace(path, '')[1:], f))
                elif 'pcvs.yml' == f or 'pcvs.yml.in' == f:
                    yaml_files.append((label, root.replace(path, '')[1:], f))

    logs.debug("Found setup files: {}".format(pprint.pformat(setup_files)))
    logs.debug("Found static files: {}".format(pprint.pformat(yaml_files)))

    logs.print_item("Execute dynamic testing scripts & Process output")
    with logs.progbar(setup_files) as iterbar:
        for label, subprefix, fname in iterbar:
            base_srcdir = path_dict[label]
            cur_srcdir = os.path.join(base_srcdir, subprefix)
            base_buildir = os.path.join(run_settings['validation']['output'], "test_suite", label)
            cur_buildir = os.path.join(base_buildir, subprefix)

            environ['pcvs_src'] = base_srcdir
            environ['pcvs_testbuild'] = base_buildir
            os.makedirs(os.path.join(base_buildir, subprefix))
            f = os.path.join(cur_srcdir, fname)
    
            res = subprocess.run([f, subprefix], env=environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode != 0:
                logs.err("Fail to run {}".format(f), "stderr: {}".format(res.stderr.decode('utf-8')), abort=1)
            out_file = os.path.join(cur_buildir, 'pcvs.yml')
            with open(out_file, 'w') as fh:
                fh.write(res.stdout.decode('utf-8'))
            
            te_node = __load_yaml_to_tree(out_file)
            final.append(descriptor.TEDescriptor(te_node))

    logs.print_item("Process YAML test files")
    with logs.progbar(yaml_files) as iterbar:
        # label = search path, given by user
        # path = associated search path, given by user
        # root = PCVS-related file prefix
        # f = filename
        for label, subprefix, fname in iterbar:
            f = os.path.join(path_dict[label], subprefix, fname)
            try:
                te_node = __load_yaml_to_tree(f)
                final.append(descriptor.TEDescriptor(te_node))
            except:
                logs.err("Failed to read the file {}".format(f))
                
    #logs.print_n_stop(final=final)


def run():
    __print_summary()
    logs.print_section("Start JCHRONOSS")

    subprocess.run([os.path.join(run_settings['validation']['output'], "cache/jchrns/install/bin/jchronoss")])
    pass


def terminate():
    logs.print_section("Build final archive")
    if shutil.which("xsltproc") is not None:
        logs.print_section("Build browsable results")
    pass