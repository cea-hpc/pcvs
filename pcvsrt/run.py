import os
import subprocess
import yaml
import shutil
import tarfile
import glob
import pprint
import pcvsrt
from pcvsrt import config, profile, descriptor, globals, logs, files, engine

run_settings = {}
descriptors = []


def __print_summary():
    global run_settings
    logs.print_section("Validation details:")
    logs.print_item("Loaded rofile: '{}'".format(run_settings['validation']['pfname']))
    logs.print_item("Build into: {}".format(run_settings['validation']['output']))
    logs.print_item("Verbosity: {}".format(logs.get_verbosity_str()))
    logs.print_item("User directories:")
    for k, v in run_settings['user_dirs'].items():
        logs.print_item("'{}': {}".format(k.upper(), v), depth=2)
    # logs.print_item(": {}".format())


def __build_jchronoss():
    global run_settings
    archive_name = None
    # Compute JCHRONOSS paths & store them
    src_prefix = os.path.join(run_settings['validation']['output'], "cache/jchrns")
    inst_prefix = os.path.join(run_settings['validation']['output'], "cache/install")
    # FIXME: Dirty way to locate the archive
    # find & extract the jchronoss archive
    for f in glob.glob(os.path.join(globals.ROOTPATH, "../**/jchronoss-*"), recursive=True):
        if 'jchronoss-' in f:
            archive_name = os.path.join(globals.ROOTPATH, f)
            break
    assert(archive_name)
    tarfile.open(os.path.join(archive_name)).extractall(src_prefix)

    # find the exact path to CMakeList.txt
    src_prefix = os.path.dirname(glob.glob(os.path.join(src_prefix, "jchronoss-*/CMakeLists.txt"))[0])

    # CD to build dir
    with files.cwd(os.path.join(src_prefix, "build")):
        command = "cmake {} -DCMAKE_INSTALL_PREFIX={} -DENABLE_OPENMP=OFF -DENABLE_COLOR={} && make install".format(
            src_prefix, inst_prefix,
            "ON" if run_settings['validation']['color'] else "OFF"
        )

        res = b''
        try:
            res = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        except Exception as e:
            logs.err("Unable to build JCHRONOSS properly", "{}".format(res.decode('utf-8')), abort=1)

    run_settings['validation']['jchronoss'] = {
        "src": src_prefix,
        "install": inst_prefix
    }

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

    logs.print_item("Check whether build directory is valid")
    buildir = os.path.join(run_settings['validation']['output'], "test_suite")
    if os.path.isdir(buildir):
        if not run_settings['validation']['override']:
            logs.err("Previous run artifacts found in {}. Please use '--override' to ignore.".format(settings['output']), abort=1)
        else:
            logs.print_item("Cleaning up {}".format(buildir), depth=2)
            shutil.rmtree(buildir)

    logs.print_item("Create subdirs for each user-labeled test directories")
    for label in dirs_dict.keys():
        os.makedirs(os.path.join(buildir, label))

    logs.print_item("Loaded profile: '{}'".format(run_settings['validation']['pfname']))
    __build_tools()

    logs.print_section("Initialize the test engine")
    engine.initialize(run_settings)


tokens = {
    '@BUILDPATH@': None,
    '@SRCPATH@': None,
    '@ROOTPATH@': None,
    '@BROOTPATH@': None,
    '@SPACKPATH@': "TBD",
    '@HOME@': os.environ['HOME'],
    '@USER@': os.environ['USER']
}


def __replace_yaml_token(stream, src, build, prefix):
    local_tokens = tokens
    local_tokens['@ROOTPATH@'] = build
    local_tokens['@BROOTPATH@'] = src
    local_tokens['@SRCPATH@'] = os.path.join(src, prefix)
    local_tokens['@BUILDPATH@'] = os.path.join(build, prefix)
    for k, v in local_tokens.items():
        stream = stream.replace(k, v)
    return stream


def __load_yaml_legacy_syntax(f):
    # barely legal to do that..;
    old_group_file = os.path.join(os.path.dirname(__file__), "templates/group-compat.yml")
    cmd = "pcvs_convert {} --stdout -k te -t {} 2>/dev/null".format(f, old_group_file)
    res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
    if res.returncode != 0:
        logs.err("Failed to convert {}".format(f), abort=1)
    return res.stdout.decode('utf-8')


def __load_yaml_to_tree(f, src, build, prefix):
    convert = False
    try:
        with open(f, 'r') as fh:
            obj = yaml.load(__replace_yaml_token(fh.read(), src, build, prefix), Loader=yaml.FullLoader)

        # TODO: Validate input & raise YAMLError if invalid
        raise yaml.YAMLError("TODO: write validation")
    except yaml.YAMLError:
        convert = True
    except Exception as e:
        logs.err("Err loading the YAML file {}:".format(f), "{}".format(e), abort=1)

    if convert:
        logs.info("Attempt to use legacy syntax for {}".format(f))
        obj = yaml.load(__replace_yaml_token(__load_yaml_legacy_syntax(f), src, build, prefix), Loader=yaml.FullLoader)
        if logs.get_verbosity('debug'):
            convert_file = os.path.join(os.path.split(f)[0], "convert-pcvs.yml")
            logs.debug("Save converted file to {}".format(convert_file))
            with open(convert_file, 'w') as fh:
                yaml.dump(obj, fh)

    return obj

def print_file_walker(elt):
    if elt is None:
        return None
    return "["+elt[0]+"] " + elt[1]

def load_benchmarks():
    global run_settings
    global descriptors

    logs.print_section("Load from filesystem")
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

    logs.print_item("Manage dynamic files (scripts)")
    with logs.progbar(setup_files, print_func=print_file_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            env = os.environ.copy()
            base_srcdir = path_dict[label]
            cur_srcdir = os.path.join(base_srcdir, subprefix)
            base_buildir = os.path.join(run_settings['validation']['output'], "test_suite", label)
            cur_buildir = os.path.join(base_buildir, subprefix)

            env['pcvs_src'] = base_srcdir
            env['pcvs_testbuild'] = base_buildir
            os.makedirs(os.path.join(base_buildir, subprefix))
            f = os.path.join(cur_srcdir, fname)
            try:
                res = subprocess.run([f, subprefix], env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
            except:
                logs.err("Fail to run {}".format(f), abort=1)
            
            out_file = os.path.join(cur_buildir, 'pcvs.yml')
            with open(out_file, 'w') as fh:
                fh.write(res.stdout.decode('utf-8'))
            
            te_node = __load_yaml_to_tree(out_file, base_srcdir, base_buildir, subprefix)
            te_base = ".".join([label, subprefix.replace("/", ".")])
            for k_elt, v_elt in te_node.items():
                te_id = ".".join([te_base, k_elt])
                final.append(descriptor.TEDescriptor(v_elt, te_id))

    logs.print_item("Process static test files")
    with logs.progbar(yaml_files, print_func=print_file_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            base_srcdir = path_dict[label]
            cur_srcdir = os.path.join(base_srcdir, subprefix)
            base_buildir = os.path.join(run_settings['validation']['output'], "test_suite", label)
            cur_buildir = os.path.join(base_buildir, subprefix)
            f = os.path.join(cur_srcdir, fname)
            try:
                te_node = __load_yaml_to_tree(f, base_srcdir, base_buildir, subprefix)
                te_base = ".".join([label, subprefix.replace("/", ".")])
                for k_elt, v_elt in te_node.items():
                    te_id = ".".join([te_base, k_elt])
                    final.append(descriptor.TEDescriptor(v_elt, te_id))
            except Exception as e:
                logs.err("Failed to read the file {}: ".format(f), "{}".format(e), abort=1)

    descriptors = final


def process_benchmarks():
    logs.print_section("Compose test-suite from benchmarks & configs")
    for desc in descriptors:
        ready = engine.process(desc)


def run():
    __print_summary()
    logs.print_item("Save Configurations for later use")
    #yaml.add_representer(pcvsrt.descriptor.TEDescriptor, pcvsrt.descriptor.representer)
    with open(os.path.join( run_settings['validation']['output'], "conf.yml"), 'w') as conf_fh:
        yaml.dump(run_settings, conf_fh)
    
    logs.print_section("Run the Orchestrator (JCHRONOSS)")
    subprocess.run([os.path.join(run_settings['validation']['jchronoss']['install'], "bin/jchronoss")])
    pass


def terminate():
    logs.print_section("Build final results archive")
    logs.print_item("Prune non-printable characters")
    logs.print_item("Remove undesired data")
    logs.print_item("Extract base information")
    logs.print_item("Save user-defined artifacts")

    if shutil.which("xsltproc") is not None:
        logs.print_section("Generate static reporting webpages")
