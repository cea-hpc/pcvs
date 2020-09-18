import glob
import os
import pathlib
import fileinput
import pprint
import shutil
import subprocess
import tarfile
from datetime import datetime
from subprocess import CalledProcessError

import yaml

from pcvsrt import criterion, test
from pcvsrt.helpers import io, log, system
from pcvsrt.test import Test, TEDescriptor


def __print_summary():
    n = system.get('validation')
    log.print_section("Summary:")
    log.print_item("Loaded profile: '{}'".format(n.pf_name))
    log.print_item("Built into: {}".format(n.output))
    log.print_item("Verbosity: {}".format(log.get_verbosity_str().capitalize()))
    log.print_item("User directories:")
    width = max([len(i) for i in n.dirs])
    for k, v in system.get('validation').dirs.items():
        log.print_item("{:<{width}}: {:<{width}}".format(k.upper(), v, width=width), depth=2)
    # log.print_item(": {}".format())


def __build_jchronoss():
    archive_name = None
    # Compute JCHRONOSS paths & store themf
    val_node = system.get('validation')
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
    #with io.cwd(os.path.join(src_prefix, "build")):
    command = "cmake {0} -B{1} -DCMAKE_INSTALL_PREFIX={2} -DENABLE_OPENMP=OFF -DENABLE_COLOR={3} && make -C {1} install".format(
        src_prefix, os.path.join(src_prefix, "build"), inst_prefix,
        "ON" if val_node.color else "OFF"
        )
    log.info("cmd: {}".format(command))
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


def prepare(run_settings):
    log.print_section("Prepare environment")
    log.print_item("build configuration tree")

    valcfg = system.get('validation')
    log.print_item("Check whether build directory is valid")
    buildir = os.path.join(valcfg.output, "test_suite")
    # if a previous build exists
    if os.path.isdir(buildir):
        if not valcfg.override:
            log.err("Previous run artifacts found in {}. Please use '--override' to ignore.".format(valcfg.output), abort=1)
        else:
            log.print_item("Cleaning up {}".format(buildir), depth=2)
            io.create_or_clean_path(buildir)
            io.create_or_clean_path(os.path.join(valcfg.output, 'webview'))
            io.create_or_clean_path(os.path.join(valcfg.output, 'conf.yml'))
            io.create_or_clean_path(os.path.join(valcfg.output, 'conf.env'))
            io.create_or_clean_path(os.path.join(valcfg.output, 'save_for_export'))
        

    log.print_item("Create subdirs for each provided directories")
    for label in valcfg.dirs.keys():
        os.makedirs(os.path.join(buildir, label))

    log.print_section("Build third-party tools")
    __build_tools()

    log.print_section("Load and initialize validation criterions")
    criterion.initialize_from_system()
    # Pick on criterion used as 'resources' by JCHRONOSS
    # this is set by the run configuration
    # TODO: replace resource here by the one read from config
    TEDescriptor.init_system_wide('n_node')


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
        log.debug("Attempt to use legacy syntax for {}".format(f))
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
    path_dict = system.get('validation').dirs
    setup_files = list()
    yaml_files = list()

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
            log.err("  - {}:  {}".format(elt[0], elt[1]))
        log.err("", abort=1)


def build_envvar_from_configuration(current_node, parent_prefix="pcvs"):
    stream = ""
    for k, v in current_node.items():
        if v is None:
            v = ''
        if isinstance(v, dict):
            stream += build_envvar_from_configuration(v, parent_prefix+"_"+k)
            continue
        elif v is None:
            v = ''
        elif isinstance(v, bool):
            v = "0" if v is False else True
        elif isinstance(v, list):
            v = "'"+" ".join(v)+"'"
        else:
            v = "'"+str(v)+"'"

        stream += "{}_{}={}\n".format(parent_prefix, k, v)
    return stream


def process_dyn_setup_scripts(setup_files):
    err = []
    log.print_item("Convert configuation to Shell variables")

    with open(os.path.join(system.get('validation').output, 'conf.env'), 'w') as fh:
        fh.write(build_envvar_from_configuration(system.get()))
        fh.close()

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
                stream +="".join([t.serialize() for t in TEDescriptor(k_elt, v_elt, label, subprefix).construct_tests()])
            system.get('validation').xmls.append(Test.finalize_file(cur_build, label, stream))
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
                stream +="".join([t.serialize() for t in TEDescriptor(k_elt, v_elt, label, subprefix).construct_tests()])
            system.get('validation').xmls.append(Test.finalize_file(cur_build, label, stream))
    return err


def run():
    __print_summary()
    log.print_item("Save Configurations into {}".format(system.get('validation').output))
    with open(os.path.join(system.get('validation').output, "conf.yml"), 'w') as conf_fh:
        yaml.dump(system.get().serialize(), conf_fh)
    
    log.print_section("Run the Orchestrator (JCHRONOSS)")

    valcfg = system.get('validation')
    macfg = system.get('machine')

    launcher = "--launcher={}".format(macfg.wrapper.alloc) if 'alloc' in macfg.wrapper else ''
    clauncher = "--compil-launcher={}".format(macfg.wrapper.run) if 'run' in macfg.wrapper else ''  
    
    cmd = [
        os.path.join(valcfg.jchronoss.install, "bin/jchronoss"),
        "--long-names",
        "--verbosity={}".format(min(2, valcfg.verbose)),
        "--build={}".format(valcfg.jchronoss.exec),
        "--nb-resources={}".format(macfg.nodes),
        "--nb-slaves={}".format(macfg.concurrent_run),
        launcher,
        clauncher,
        "--output-format={}".format(",".join(valcfg.result.format)),
        "--expect-success",
        "--keep={}".format(valcfg.result.log),
        "--policy={}".format(0),
        "--maxt-slave={}".format(macfg.batch_maxtime),
        "--mint-slave={}".format(macfg.batch_mintime),
        "--size-flow={}".format(valcfg.result.logsz),
        "--autokill={}".format(100000),
        "--fake" if valcfg.simulated else ""
       ] + valcfg.xmls
    
    # Filtering is required to prune
    # empty strings (translated to './.' through subprocess)
    cmd = list(filter(None, cmd))
    
    log.info("cmd: '{}'".format(" ".join(cmd)))
    try:
        #raise subprocess.CalledProcessError()
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        log.err("JCHRONOSS returned non-zero exit code!", abort=1)


def anonymize_line(line):
    print(line)
    return line \
            .replace(os.environ['HOME'], '${HOME}') \
            .replace(os.environ['USER'], '${USER}')

def anonymize_archive():
    config = system.get('validation')
    archive_prefix = os.path.join(config.output, 'save_for_export')
    outdir = config.output
    for root, dirs, files in os.walk(archive_prefix):
        for f in files:
            if not (f.endswith(('.xml', '.json', '.yml', '.txt', '.md', '.html'))):
                continue
            with fileinput.FileInput(os.path.join(root, f),
                                     inplace=True,
                                     backup=".raw") as fh:
                for line in fh:
                    print(
                        line.replace(outdir, '${PCVS_RUN_DIRECTORY}')
                            .replace(os.environ['HOME'], '${HOME}')
                            .replace(os.environ['USER'], '${USER}'),
                        end='')
            

def save_for_export(f, dest=None):
    config = system.get('validation')
    # if dest is not given, 'dest' will be the same dirtree with
    # extra 'safe_for_export' sudir below 'outdir'
    # otherwise, just use the given dest instead of replacing
    if dest is None:
        dest = f
    dest = dest.replace(config.output, os.path.join(config.output, 'save_for_export'))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    
    try:
        if os.path.isfile(f):
            shutil.copyfile(f, dest)
        elif os.path.isdir(f):
            shutil.copytree(f, dest)
        else:
            log.err("{}".format(f))
    except FileNotFoundError as e:
        log.warn("Unable to copy {}:".format(f), '{}'.format(e))


def terminate():
    archive_name = "pcvsrun_{}".format(datetime.now().strftime('%Y%m%d%H%M%S'))
    outdir = system.get('validation').output

    if shutil.which("xsltproc") is not None:
        log.print_section("Generate static reporting webpages")
        try:
            cmd = [
                os.path.join(system.get('validation').jchronoss.src,
                             'tools/webview/webview_gen_all.sh'),
                "--new={}".format(os.path.join(outdir, "test_suite"))
            ]
            log.info('cmd: {}'.format(" ".join(cmd)))
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL)
            log.print_item("Browsing: {}".format(
                os.path.join(system.get('validation').jchronoss.src,
                             'tools/webview/webview/generated/main.html')))
        except (CalledProcessError, FileNotFoundError) as e:
            log.warn("Unable to run the webview:", "{}".format(e))

    log.print_section("Prepare results for export")

    log.print_item("Save results")
    # copy file before anonymizing them
    for root, dirs, files in os.walk(os.path.join(outdir, "test_suite")):
        for file in files:
            # TODO: save user-defined artifacts
            if file.endswith(('.json', '.xml', '.yml')):
                save_for_export(os.path.join(root, file))

    save_for_export(os.path.join(outdir, 'conf.yml'))
    save_for_export(os.path.join(outdir, 'conf.env'))
    save_for_export(os.path.join(system.get('validation').jchronoss.src,
                                 "tools/webview"),
                    os.path.join(outdir, 'webview'))

    if system.get('validation').anonymize:
        log.print_item("Anonymize the final archive")
        anonymize_archive()

    log.print_item("Save user-defined artifacts")
    log.warn('TODO user-defined artifact')

    log.print_item("Generate the archive")

    with io.cwd(outdir):
        cmd = [
            "tar",
            "czf",
            "{0}.tar.gz".format(archive_name),
            "save_for_export"
        ]
        try:
            log.info('cmd: {}'.format(" ".join(cmd)))
            subprocess.check_call(cmd)
        except CalledProcessError as e:
            log.err("Fail to create an archive:", "{}".format(e), abort=1)
