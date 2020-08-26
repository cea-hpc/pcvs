import glob
import os
import pathlib
import pprint
import shutil
import subprocess
import tarfile
from subprocess import CalledProcessError

import yaml

from pcvsrt import config, engine, profile, test
from pcvsrt.helpers import io, log
from pcvsrt.helpers.system import sysTable


def __print_summary():
    n = sysTable.validation
    log.print_section("Validation details:")
    log.print_item("Loaded profile: '{}'".format(n.pfname))
    log.print_item("Built into: {}".format(n.output))
    log.print_item("Verbosity: {}".format(log.get_verbosity_str().capitalize()))
    log.print_item("User directories:")
    width = max([len(i) for i in sysTable.rootdirs])
    for k, v in sysTable.rootdirs.items():
        log.print_item("{:<{width}}: {:<{width}}".format(k.upper(), v, width=width), depth=2)
    # log.print_item(": {}".format())


def __build_jchronoss():
    archive_name = None
    # Compute JCHRONOSS paths & store themf
    val_node = sysTable.validation
    src_prefix = os.path.join(val_node.output, "cache/src")
    inst_prefix = os.path.join(val_node.output, "cache/install")
    exec_prefix = os.path.join(val_node.output, "cache/exec")
    # FIXME: Dirty way to locate the archive
    # find & extract the jchronoss archive
    for f in glob.glob(os.path.join(io.ROOTPATH, "../**/jchronoss-*"), recursive=True):
        if 'jchronoss-' in f:
            archive_name = os.path.join(io.ROOTPATH, f)
            break
    assert(archive_name)
    tarfile.open(os.path.join(archive_name)).extractall(src_prefix)

    # find the exact path to CMakeList.txt
    src_prefix = os.path.dirname(glob.glob(os.path.join(
                                src_prefix, "jchronoss-*/CMakeLists.txt"))[0])

    # CD to build dir
    with io.cwd(os.path.join(src_prefix, "build")):
        command = "cmake {} -DCMAKE_INSTALL_PREFIX={} -DENABLE_OPENMP=OFF -DENABLE_COLOR={} && make install".format(
            src_prefix, inst_prefix,
            "ON" if val_node.color else "OFF"
        )
        try:
            _ = subprocess.check_call(
                command, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        except CalledProcessError:
            log.err("Failed to build JCHRONOSS:", abort=1)

    io.create_or_clean_path(exec_prefix)

    val_node.jchronoss.src = src_prefix
    val_node.jchronoss.exec = exec_prefix 
    val_node.jchronoss.install = inst_prefix


def __setup_webview():
    pass


def __build_tools():
    log.print_item("job orchestrator (JCHRONOSS)")
    __build_jchronoss()
    log.print_item("Web-based reporting tool")
    __setup_webview()


def prepare(run_settings, dirs_dict, pf):
    log.print_section("Prepare environment")
    log.print_item("build configuration tree")

    sysTable.validation = run_settings
    sysTable.validation.xmls = list()
    sysTable.rootdirs = dirs_dict
    sysTable.compiler = pf.compiler
    sysTable.runtime = pf.runtime
    sysTable.group = pf.group
    sysTable.machine = pf.machine
    sysTable.criterion = pf.criterion

    log.print_item("Check whether build directory is valid")
    buildir = os.path.join(sysTable.validation.output, "test_suite")
    # if a previous build exists
    if os.path.isdir(buildir):
        if not sysTable.validation.force:
            log.err("Previous run artifacts found in {}. Please use '--override' to ignore.".format(sysTable.validation.output), abort=1)
        else:
            log.print_item("Cleaning up {}".format(buildir), depth=2)
            io.create_or_clean_path(buildir)

    log.print_item("Create subdirs for each provided directories")
    for label in sysTable.rootdirs.keys():
        os.makedirs(os.path.join(buildir, label))

    log.print_section("Build third-party tools")
    __build_tools()

    log.print_section("Initialize the test engine")
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
        log.err("Err loading the YAML file {}:".format(f), "{}".format(e), abort=1)

    if convert:
        log.info("Attempt to use legacy syntax for {}".format(f))
        obj = yaml.load(__replace_yaml_token(__load_yaml_file_legacy(f), src, build, prefix), Loader=yaml.FullLoader)
        if log.get_verbosity('debug'):
            convert_file = os.path.join(os.path.split(f)[0], "convert-pcvs.yml")
            log.debug("Save converted file to {}".format(convert_file))
            with open(convert_file, 'w') as fh:
                yaml.dump(obj, fh)
    return obj


def __print_progbar_walker(elt):
    if elt is None:
        return None
    return "["+elt[0]+"] " + elt[1]


def process():
    log.print_section("Load from filesystem")
    path_dict = sysTable.rootdirs
    setup_files = list()
    yaml_files = list()

    log.info("Discovery user directories: {}".format(pprint.pformat(path_dict)))
    # discovery may take a while with some systems
    log.print_item("PCVS-related file detection")
    # iterate over user directories
    for label, path in path_dict.items():
        # for each, walk through the tree
        for root, dirs, list_files in os.walk(path):
            last_dir = os.path.basename(root)
            # if the current dir is a 'special' one, discard
            if last_dir in ['.pcvsrt', '.pcvs', "build_scripts"]:
                log.debug("skip {}".format(root))
                # set dirs to null, avoiding os.wal() to go further in that dir
                dirs[:] = []
                continue
            # otherwise, save the file
            for f in list_files:
                # [1:] to remove extra '/'
                if 'pcvs.setup' == f:
                    setup_files.append((label, root.replace(path, '')[1:], f))
                elif 'pcvs.yml' == f or 'pcvs.yml.in' == f:
                    yaml_files.append((label, root.replace(path, '')[1:], f))

    log.debug("Found setup files: {}".format(pprint.pformat(setup_files)))
    log.debug("Found static files: {}".format(pprint.pformat(yaml_files)))

    errors = []
    errors += process_dyn_setup_scripts(setup_files)
    errors += process_static_yaml_files(yaml_files)

    log.print_item("Checking for errors")
    if len(errors):
        log.err("Issues while loading benchmarks:")
        for elt in errors:
            log.err("  - {}: {}".format(elt[0], elt[1]))
        log.err("", abort=1)


def process_dyn_setup_scripts(setup_files):
    err = []
    log.print_item("Manage dynamic files (scripts)")
    with log.progbar(setup_files, print_func=__print_progbar_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            base_src, cur_src, base_build, cur_build = io.generate_local_variables(label, subprefix)
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
            sysTable.validation.xmls.append(engine.finalize_file(cur_build, label, stream))
    return err  

def process_static_yaml_files(yaml_files):
    err = []
    log.print_item("Process static test files")
    with log.progbar(yaml_files, print_func=__print_progbar_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            base_src, cur_src, base_build, cur_build = io.generate_local_variables(label, subprefix)
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
                log.err("Failed to read the file {}: ".format(f), "{}".format(e), abort=1)
            for k_elt, v_elt in te_node.items():
                stream +="".join([t.serialize() for t in test.TEDescriptor(k_elt, v_elt, label, subprefix).construct_tests()])
            sysTable.validation.xmls.append(engine.finalize_file(cur_build, label, stream))
    return err


def run():
    __print_summary()
    log.print_item("Save Configurations for later use")
    with open(os.path.join(sysTable.validation.output, "conf.yml"), 'w') as conf_fh:
        yaml.dump(sysTable.serialize(), conf_fh)
    
    log.print_section("Run the Orchestrator (JCHRONOSS)")

    prog = os.path.join(sysTable.validation.jchronoss.install, "bin/jchronoss")
    build = os.path.join(sysTable.validation.jchronoss.exec)
    verb = min(2, sysTable.validation.verbose)
    files = sysTable.validation.xmls

    cmd = [
        prog,
        "--verbosity={}".format(verb),
        "--build", build,
        "--nb-resources={}".format(sysTable.machine.nodes)
       ] + files
    
    log.info("JCHRONOSS: '{}'".format(" ".join(cmd)))
    try:
        #raise subprocess.CalledProcessError()
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        log.err("JCHRONOSS returned non-zero exit code!", abort=1)


def terminate():
    log.print_section("Build final results archive")
    log.print_item("Prune non-printable characters")
    log.print_item("Remove undesired data")
    log.print_item("Extract base information")
    log.print_item("Save user-defined artifacts")

    if shutil.which("xsltproc") is not None:
        log.print_section("Generate static reporting webpages")
