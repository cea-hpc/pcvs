import os
import subprocess
from subprocess import CalledProcessError
import yaml
import shutil
import tarfile
import glob
import pprint
import pathlib
import addict
import pcvsrt
from pcvsrt import config, profile, test, globals, logs, files, engine, helper, context
from pcvsrt.context import settings

def __print_summary():
    global run_settings
    n = settings.validation
    logs.print_section("Validation details:")
    logs.print_item("Loaded profile: '{}'".format(n.pfname))
    logs.print_item("Built into: {}".format(n.output))
    logs.print_item("Verbosity: {}".format(logs.get_verbosity_str().capitalize()))
    logs.print_item("User directories:")
    width = max([len(i) for i in settings.rootdirs])
    for k, v in settings.rootdirs.items():
        logs.print_item("{:<{width}}: {:<{width}}".format(k.upper(), v, width=width), depth=2)
    # logs.print_item(": {}".format())


def __build_jchronoss():
    global run_settings
    archive_name = None
    # Compute JCHRONOSS paths & store themf
    val_node = settings.validation
    src_prefix = os.path.join(val_node.output, "cache/src")
    inst_prefix = os.path.join(val_node.output, "cache/install")
    exec_prefix = os.path.join(val_node.output, "cache/exec")
    # FIXME: Dirty way to locate the archive
    # find & extract the jchronoss archive
    for f in glob.glob(os.path.join(globals.ROOTPATH, "../**/jchronoss-*"), recursive=True):
        if 'jchronoss-' in f:
            archive_name = os.path.join(globals.ROOTPATH, f)
            break
    assert(archive_name)
    tarfile.open(os.path.join(archive_name)).extractall(src_prefix)

    # find the exact path to CMakeList.txt
    src_prefix = os.path.dirname(glob.glob(os.path.join(
                                src_prefix, "jchronoss-*/CMakeLists.txt"))[0])

    # CD to build dir
    with files.cwd(os.path.join(src_prefix, "build")):
        command = "cmake {} -DCMAKE_INSTALL_PREFIX={} -DENABLE_OPENMP=OFF -DENABLE_COLOR={} && make install".format(
            src_prefix, inst_prefix,
            "ON" if val_node.color else "OFF"
        )
        try:
            _ = subprocess.check_call(command, shell=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        except CalledProcessError as e:
            logs.err("Failed to build JCHRONOSS:", abort=1)

    globals.create_or_clean_path(exec_prefix)

    val_node.jchronoss.src = src_prefix
    val_node.jchronoss.exec = exec_prefix 
    val_node.jchronoss.install = inst_prefix


def __setup_webview():
    pass

def __build_tools():
    
    logs.print_item("job orchestrator (JCHRONOSS)")
    __build_jchronoss()

    logs.print_item("Web-based reporting tool")
    __setup_webview()


def prepare(run_settings, dirs_dict, profile):
    
    logs.print_section("Prepare environment")
    logs.print_item("build configuration tree")

    settings.validation = run_settings
    settings.validation.xmls = list()
    settings.rootdirs = dirs_dict
    settings.compiler = profile.compiler
    settings.runtime = profile.runtime
    settings.group = profile.group
    settings.machine = profile.machine
    settings.criterion = profile.criterion

    logs.print_item("Check whether build directory is valid")
    buildir = os.path.join(settings.validation.output, "test_suite")
    # if a previous build exists
    if os.path.isdir(buildir):
        if not settings.validation.force:
            logs.err("Previous run artifacts found in {}. Please use '--override' to ignore.".format(settings.validation.output), abort=1)
        else:
            logs.print_item("Cleaning up {}".format(buildir), depth=2)
            globals.create_or_clean_path(buildir)

    logs.print_item("Create subdirs for each provided directories")
    for label in settings.rootdirs.keys():
        os.makedirs(os.path.join(buildir, label))

    logs.print_section("Build third-party tools")
    __build_tools()

    logs.print_section("Initialize the test engine")
    engine.initialize()



def __replace_yaml_token(stream, src, build, prefix):   
    tokens = {
        '@BUILDPATH@': os.path.join(build, prefix),
        '@SRCPATH@': os.path.join(src, prefix),
        '@ROOTPATH@': src,
        '@BROOTPATH@': build,
        '@SPACKPATH@': "TBD",
        '@HOME@': str(pathlib.Path.home()),
        '@USER@': os.getlogin()
    }
    for k, v in tokens.items():
        stream = stream.replace(k, v)
    return stream


def __load_yaml_file_legacy(f):
    # barely legal to do that...
    old_group_file = os.path.join(os.path.dirname(__file__), "templates/group-compat.yml")
    cmd = "pcvs_convert {} --stdout -k te -t {} 2>/dev/null".format(f, old_group_file)
    out = subprocess.check_output(cmd, shell=True)
    return out.decode('utf-8')


def __load_yaml_file(f, src, build, prefix):
    convert = False
    obj = {}
    try:
        with open(f, 'r') as fh:
            obj = yaml.load(__replace_yaml_token(fh.read(), src, build, prefix), Loader=yaml.FullLoader)

        # TODO: Validate input & raise YAMLError if invalid
        #raise yaml.YAMLError("TODO: write validation")
    except yaml.YAMLError:
        convert = True
    except Exception as e:
        logs.err("Err loading the YAML file {}:".format(f), "{}".format(e), abort=1)

    if convert:
        logs.info("Attempt to use legacy syntax for {}".format(f))
        obj = yaml.load(__replace_yaml_token(__load_yaml_file_legacy(f), src, build, prefix), Loader=yaml.FullLoader)
        if logs.get_verbosity('debug'):
            convert_file = os.path.join(os.path.split(f)[0], "convert-pcvs.yml")
            logs.debug("Save converted file to {}".format(convert_file))
            with open(convert_file, 'w') as fh:
                yaml.dump(obj, fh)
    return obj


def __print_progbar_walker(elt):
    if elt is None:
        return None
    return "["+elt[0]+"] " + elt[1]


def process():
    logs.print_section("Load from filesystem")
    path_dict = settings.rootdirs
    setup_files = list()
    yaml_files = list()

    logs.info("Discovery user directories: {}".format(pprint.pformat(path_dict)))
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

    errors = []
    errors += process_dyn_setup_scripts(setup_files)
    errors += process_static_yaml_files(yaml_files)

    logs.print_item("Checking for errors")
    if len(errors):
        logs.err("Issues while loading benchmarks:")
        for elt in errors:
            logs.err("  - {}: {}".format(elt[0], elt[1]))
        logs.err("", abort=1)


def process_dyn_setup_scripts(setup_files):
    err = []
    logs.print_item("Manage dynamic files (scripts)")
    with logs.progbar(setup_files, print_func=__print_progbar_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            base_src, cur_src, base_build, cur_build = helper.generate_local_variables(label, subprefix)
            env = os.environ.copy()
            
            env['pcvs_src'] = base_src
            env['pcvs_testbuild'] = base_build

            if not os.path.isdir(cur_build):
                os.makedirs(cur_build)
            f = os.path.join(cur_src, fname)
            try:
                out = subprocess.check_output([f, subprefix], env=env,
                                              stderr=subprocess.DEVNULL)
                out_file = os.path.join(cur_build, 'pcvs.yml')
                with open(out_file, 'w') as fh:
                    fh.write(out.decode('utf-8'))
                te_node = __load_yaml_file(out_file, base_src, base_build, subprefix)
            except CalledProcessError as e:
                err += [(f, e)]
                continue
            stream = ""
            for k_elt, v_elt in te_node.items():
                stream +="".join([t.serialize() for t in test.TEDescriptor(k_elt, v_elt, label, subprefix).construct_tests()])
            settings.validation.xmls.append(engine.finalize_file(cur_build, label, stream))
    return err  

def process_static_yaml_files(yaml_files):
    err = []
    logs.print_item("Process static test files")
    with logs.progbar(yaml_files, print_func=__print_progbar_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            base_src, cur_src, base_build, cur_build = helper.generate_local_variables(label, subprefix)
            if not os.path.isdir(cur_build):
                os.makedirs(cur_build)
            f = os.path.join(cur_src, fname)
            stream = ""
            try:
                te_node = __load_yaml_file(f, base_src, base_build, subprefix)
            except (yaml.YAMLError, CalledProcessError) as e:
                err += [(f, e)]
                continue
            except Exception as e:
                logs.err("Failed to read the file {}: ".format(f), "{}".format(e), abort=1)
            for k_elt, v_elt in te_node.items():
                stream +="".join([t.serialize() for t in test.TEDescriptor(k_elt, v_elt, label, subprefix).construct_tests()])
            settings.validation.xmls.append(engine.finalize_file(cur_build, label, stream))
    return err


def run():
    __print_summary()
    logs.print_item("Save Configurations for later use")
    with open(os.path.join(settings.validation.output, "conf.yml"), 'w') as conf_fh:
        yaml.dump(context.serialize(), conf_fh)
    
    logs.print_section("Run the Orchestrator (JCHRONOSS)")

    prog = os.path.join(settings.validation.jchronoss.install, "bin/jchronoss")
    build = os.path.join(settings.validation.jchronoss.exec)
    verb = min(2, settings.validation.verbose)
    files = settings.validation.xmls

    cmd = [
        prog,
        "--verbosity={}".format(verb),
        "--build", build,
        "--nb-resources={}".format(settings.machine.nodes)
       ] + files
    
    logs.info("JCHRONOSS: '{}'".format(" ".join(cmd)))
    try:
        raise subprocess.CalledProcessError()
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        logs.err("JCHRONOSS returned non-zero exit code!", abort=1)


def terminate():
    logs.print_section("Build final results archive")
    logs.print_item("Prune non-printable characters")
    logs.print_item("Remove undesired data")
    logs.print_item("Extract base information")
    logs.print_item("Save user-defined artifacts")

    if shutil.which("xsltproc") is not None:
        logs.print_section("Generate static reporting webpages")