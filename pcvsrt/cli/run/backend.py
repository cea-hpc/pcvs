import glob
import os
import pathlib
import fileinput
import pprint
import shutil
import subprocess
import tarfile
from datetime import date, datetime
from subprocess import CalledProcessError

import yaml

from pcvsrt import criterion, test
from pcvsrt.helpers import io, log, system, lowtest
from pcvsrt.test import TestFile, TEDescriptor


def __print_summary():
    n = system.get('validation')
    log.print_section("Summary:")
    log.print_item("Loaded profile: '{}'".format(n.pf_name))
    log.print_item("Built into: {}".format(n.output))
    log.print_item("Verbosity: {}".format(log.get_verbosity_str().capitalize()))
    log.print_item("Max sys. combinations per TE: {}".format(lowtest.max_number_of_combinations()))
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
        log.err("Failed to build JCHRONOSS:")

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
    log.print_item("Date: {}".format(
        system.get('validation').datetime.strftime("%c")))
    log.print_item("build configuration tree")

    valcfg = system.get('validation')
    log.print_item("Check whether build directory is valid")
    buildir = os.path.join(valcfg.output, "test_suite")
    # if a previous build exists
    if os.path.isdir(buildir):
        if not valcfg.override:
            log.err("Previous run artifacts found in {}. Please use '--override' to ignore.".format(valcfg.output))
        else:
            log.print_item("Cleaning up {}".format(buildir), depth=2)
            io.create_or_clean_path(buildir)
            io.create_or_clean_path(os.path.join(valcfg.output, '.pcvs_build'), is_dir=False)
            io.create_or_clean_path(os.path.join(valcfg.output, 'webview'))
            io.create_or_clean_path(os.path.join(valcfg.output, 'conf.yml'), is_dir=False)
            io.create_or_clean_path(os.path.join(valcfg.output, 'conf.env'), is_dir=False)
            io.create_or_clean_path(os.path.join(valcfg.output, 'save_for_export'))
        

    log.print_item("Create subdirs for each provided directories")
    os.makedirs(buildir)
    for label in valcfg.dirs.keys():
        os.makedirs(os.path.join(buildir, label))
    open(os.path.join(valcfg.output, '.pcvs_build'), 'w').close()
    

    log.print_section("Build third-party tools")
    __build_tools()

    log.print_section("Load and initialize validation criterions")
    criterion.initialize_from_system()
    # Pick on criterion used as 'resources' by JCHRONOSS
    # this is set by the run configuration
    # TODO: replace resource here by the one read from config
    TEDescriptor.init_system_wide('n_node')


def __print_progbar_walker(elt):
    if elt is None:
        return None
    return "["+elt[0]+"] " + elt[1]

def find_files_to_process(path_dict):
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
    return (setup_files, yaml_files)

def process():
    log.print_section("Load from filesystem")
    setup_files, yaml_files = find_files_to_process(system.get('validation').dirs)
    
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
        log.err("")


def build_env_from_configuration(current_node, parent_prefix="pcvs"):
    env_dict = dict()
    for k, v in current_node.items():
        if v is None:
            v = ''
        if isinstance(v, dict):
            env_dict.update(build_env_from_configuration(v, parent_prefix+"_"+k))
            continue
        elif v is None:
            v = ''
        elif isinstance(v, list):
            v =  " ".join(map(str, v))
        else:
            v = str(v)

        k = "{}_{}".format(parent_prefix, k).replace('.', '_')
        env_dict[k] = v
        
    return env_dict


def __str_dict_as_envvar(d):
    return "\n".join(["{}='{}'".format(i, d[i]) for i in sorted(d.keys())])


def process_dyn_setup_scripts(setup_files):
    err = []
    log.print_item("Convert configuation to Shell variables")
    env = os.environ.copy()
    env.update(build_env_from_configuration(system.get()))

    with open(os.path.join(system.get('validation').output, 'conf.env'), 'w') as fh:
        fh.write(__str_dict_as_envvar(env))
        fh.close()
    
    log.print_item("Manage dynamic files (scripts)")
    with log.progbar(setup_files, print_func=__print_progbar_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            log.info("process {} ({})".format(subprefix, label))
            base_src, cur_src, base_build, cur_build = io.generate_local_variables(label, subprefix)
            
            env['pcvs_src'] = base_src
            env['pcvs_testbuild'] = base_build

            if not os.path.isdir(cur_build):
                os.makedirs(cur_build)
            f = os.path.join(cur_src, fname)
            try:
                fds = subprocess.Popen([f, subprefix], env=env,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
                fdout, fderr = fds.communicate()
                if fds.returncode != 0:
                    err.append((f, fderr.decode('utf-8')))
                    log.err("{}: {}".format(f, fderr.decode('utf-8')))
                    continue
                out_file = os.path.join(cur_build, 'pcvs.yml')

                with open(out_file, 'w') as fh:
                    fh.write(fdout.decode('utf-8'))
                te_node = test.load_yaml_file(out_file, base_src, base_build, subprefix)
            except CalledProcessError as e:
                pass
    
            if te_node is None:  # empty file
                continue

            tf = TestFile(file_in=out_file,
                          path_out=cur_build,
                          data=te_node,
                          label=label,
                          prefix=subprefix)
            
            tf.start_process()
            system.get('validation').xmls.append(tf.flush_to_disk())
    return err

def process_static_yaml_files(yaml_files):
    err = []
    log.print_item("Process static test files")
    with log.progbar(yaml_files, print_func=__print_progbar_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            _, cur_src, _, cur_build = io.generate_local_variables(label, subprefix)
            if not os.path.isdir(cur_build):
                os.makedirs(cur_build)
            f = os.path.join(cur_src, fname)

            try:
                tf = TestFile(file_in=f,
                              path_out=cur_build,
                              label=label,
                              prefix=subprefix)
            except (yaml.YAMLError, CalledProcessError) as e:
                print(f, e)
                err.append((f, e.output))
                continue
            except Exception as e:
                log.err("Failed to read the file {}: ".format(f), "{}".format(e))
            
            tf.start_process()
            system.get('validation').xmls.append(tf.flush_to_disk())
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
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        pass
        #log.err("JCHRONOSS returned non-zero exit code!")


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
    archive_name = "pcvsrun_{}.tar.gz".format(
        system.get('validation').datetime.strftime('%Y%m%d%H%M%S'))
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
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.print_item("Browsing: {}".format(
                os.path.join(system.get('validation').jchronoss.src,
                             'tools/webview/webview/generated/main.html')))
        except (CalledProcessError, FileNotFoundError) as e:
            pass
            #log.warn("Unable to run the webview!")

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
            "{}".format(archive_name),
            "save_for_export"
        ]
        try:
            log.info('cmd: {}'.format(" ".join(cmd)))
            subprocess.check_call(cmd)
        except CalledProcessError as e:
            log.err("Fail to create an archive:", "{}".format(e))
    
    return archive_name
