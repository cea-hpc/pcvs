import fileinput
import glob
import os
import pprint
import shutil
import subprocess
import tarfile
from shutil import SameFileError
from subprocess import CalledProcessError

import yaml
from addict import Dict

from pcvs import BACKUP_NAMEDIR, BUILD_IDFILE, BUILD_NAMEDIR, ROOTPATH
from pcvs.helpers import criterion, log, system, test, utils
from pcvs.helpers.test import TEDescriptor, TestFile


def __print_summary():
    n = system.get('validation')
    log.print_section("Summary:")
    log.print_item("Loaded profile: '{}'".format(n.pf_name))
    log.print_item("Built into: {}".format(n.output))
    log.print_item("Verbosity: {}".format(
        log.get_verbosity_str().capitalize()))
    log.print_item("User directories:")
    width = max([len(i) for i in n.dirs])
    for k, v in system.get('validation').dirs.items():
        log.print_item("{:<{width}}: {:<{width}}".format(
            k.upper(),
            v,
            width=width),
            depth=2)


def __build_tools():
    archive_name = None
    # Compute JCHRONOSS paths & store themf
    val_node = system.get('validation')
    src_prefix = os.path.join(val_node.output, "cache/src")
    inst_prefix = os.path.join(val_node.output, "cache/install")
    exec_prefix = os.path.join(val_node.output, "cache/exec")
    # FIXME: Dirty way to locate the archive
    # find & extract the jchronoss archive
    for f in glob.glob(os.path.join(ROOTPATH, "../**/jchronoss-*"),
                       recursive=True):
        if 'jchronoss-' in f:
            archive_name = os.path.join(ROOTPATH, f)
            break

    if archive_name is None:
        log.err("JCHRONOSS source archive has not been found.",
                "For development purpose, JCHRONOSS hasn't been added to PCVS",
                "Please add manually the archive under {}".format(ROOTPATH))

    tarfile.open(os.path.join(archive_name)).extractall(src_prefix)

    # find the exact path to CMakeList.txt
    src_prefix = os.path.dirname(glob.glob(os.path.join(
        src_prefix, "jchronoss-*/CMakeLists.txt"))[0])
    build_prefix = os.path.join(src_prefix, "build")

    # CD to build dir
    command = "".join([
        "cmake {} -B{} -DCMAKE_INSTALL_PREFIX={}".format(src_prefix,
                                                         build_prefix,
                                                         inst_prefix),
        " -DENABLE_OPENMP=OFF -DENABLE_COLOR={}".format(
            "ON" if val_node.color else "OFF"
        ),
        " && make -C {} install".format(build_prefix)
    ])
    log.info("cmd: {}".format(command))
    try:
        _ = subprocess.check_call(
            command, shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except CalledProcessError:
        log.err("Failed to build JCHRONOSS:")

    utils.create_or_clean_path(exec_prefix)

    val_node.jchronoss.src = src_prefix
    val_node.jchronoss.exec = exec_prefix
    val_node.jchronoss.install = inst_prefix


def __check_defined_program_validity():
    # exhaustive list of user-defined program to exist before starting:
    utils.check_valid_program(system.get(
        'machine').job_manager.allocate.program)
    utils.check_valid_program(system.get(
        'machine').job_manager.allocate.wrapper)
    utils.check_valid_program(system.get('machine').job_manager.run.program)
    utils.check_valid_program(system.get('machine').job_manager.run.wrapper)
    utils.check_valid_program(system.get('machine').job_manager.batch.program)
    utils.check_valid_program(system.get('machine').job_manager.batch.wrapper)
    return
    # need to handle package_manager commands to process below
    # maybe a dummy testfile should be used
    utils.check_valid_program(system.get('compiler').commands.cc)
    utils.check_valid_program(system.get('compiler').commands.cxx)
    utils.check_valid_program(system.get('compiler').commands.fc)
    utils.check_valid_program(system.get('compiler').commands.f77)
    utils.check_valid_program(system.get('compiler').commands.f90)
    utils.check_valid_program(system.get('runtime').program)


def prepare():
    log.print_section("Prepare environment")
    log.print_item("Date: {}".format(
        system.get('validation').datetime.strftime("%c")))
    valcfg = system.get('validation')

    log.print_item("Check whether build directory is valid")
    buildir = os.path.join(valcfg.output, "test_suite")
    # if a previous build exists
    if os.path.isdir(buildir):
        if not valcfg.override:
            log.err("Old run artifacts found in {}.".format(valcfg.output),
                    "Please use '--override' to ignore.")
        else:
            if valcfg.reused_build is None:
                log.print_item("Cleaning up {}".format(buildir), depth=2)
                utils.create_or_clean_path(buildir)
            utils.create_or_clean_path(os.path.join(
                valcfg.output, BUILD_IDFILE), is_dir=False)
            utils.create_or_clean_path(os.path.join(valcfg.output, 'webview'))
            utils.create_or_clean_path(os.path.join(
                valcfg.output, 'conf.yml'), is_dir=False)
            utils.create_or_clean_path(os.path.join(
                valcfg.output, 'conf.env'), is_dir=False)
            utils.create_or_clean_path(os.path.join(
                valcfg.output, 'save_for_export'))

    log.print_item("Create subdirs for each provided directories")
    os.makedirs(buildir, exist_ok=True)
    for label in valcfg.dirs.keys():
        os.makedirs(os.path.join(buildir, label), exist_ok=True)
    open(os.path.join(valcfg.output, BUILD_IDFILE), 'w').close()

    log.print_section("Build third-party tools")
    __build_tools()

    log.print_section("Ensure user-defined programs exist")
    __check_defined_program_validity()

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
            if last_dir in [BACKUP_NAMEDIR, BUILD_NAMEDIR, "build_scripts"]:
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
    setup_files, yaml_files = find_files_to_process(
        system.get('validation').dirs)

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
            env_dict.update(build_env_from_configuration(
                v, parent_prefix+"_"+k))
            continue
        elif v is None:
            v = ''
        elif isinstance(v, list):
            v = " ".join(map(str, v))
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

    env_script = os.path.join(system.get('validation').output, 'conf.env')
    with open(env_script, 'w') as fh:
        fh.write(__str_dict_as_envvar(env))
        fh.close()

    log.print_item("Manage dynamic files (scripts)")
    with log.progbar(setup_files, print_func=__print_progbar_walker) as itbar:
        for label, subprefix, fname in itbar:
            log.info("process {} ({})".format(subprefix, label))
            base_src, cur_src, base_build, cur_build = utils.generate_local_variables(
                label, subprefix)

            env['pcvs_src'] = base_src
            env['pcvs_testbuild'] = base_build
            te_node = None
            out_file = None

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
                te_node = test.load_yaml_file(
                    out_file, base_src, base_build, subprefix)
            except CalledProcessError:
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
            _, cur_src, _, cur_build = utils.generate_local_variables(
                label, subprefix)
            if not os.path.isdir(cur_build):
                os.makedirs(cur_build)
            f = os.path.join(cur_src, fname)

            try:
                tf = TestFile(file_in=f,
                              path_out=cur_build,
                              label=label,
                              prefix=subprefix)
                tf.start_process()
                system.get('validation').xmls.append(tf.flush_to_disk())
            except (yaml.YAMLError, CalledProcessError) as e:
                print(f, e)
                err.append((f, e.output))
                continue
            except Exception as e:
                log.err("Failed to read {}: ".format(f), "{}".format(e))
    return err


def run():
    __print_summary()
    log.print_item("Save Configurations into {}".format(
        system.get('validation').output))

    conf_file = os.path.join(system.get('validation').output, "conf.yml")
    with open(conf_file, 'w') as conf_fh:
        yaml.dump(system.get().serialize(), conf_fh, default_flow_style=None)

    log.print_section("Run the Orchestrator (JCHRONOSS)")

    valcfg = system.get('validation')
    macfg = system.get('machine')

    launcher = ""
    if 'wrapper' in macfg.job_manager.allocate:
        launcher = "--launcher={}".format(macfg.job_manager.allocate.wrapper)

    clauncher = ""
    if 'wrapper' in macfg.job_manager.run:
        clauncher = "--compil-launcher={}".format(
            macfg.job_manager.run.wrapper)

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
        "--maxt-slave={}".format(macfg.job_manager.maxtime),
        "--mint-slave={}".format(macfg.job_manager.mintime),
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
        # log.err("JCHRONOSS returned non-zero exit code!")


def anonymize_archive():
    config = system.get('validation')
    archive_prefix = os.path.join(config.output, 'save_for_export')
    outdir = config.output
    for root, _, files in os.walk(archive_prefix):
        for f in files:
            if not f.endswith(('.xml', '.json', '.yml',
                               '.txt', '.md', '.html')):
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
    dest = dest.replace(config.output, os.path.join(
        config.output, 'save_for_export'))
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
    
    log.print_section("Exporting results")

    if shutil.which("xsltproc") is not None:
        log.print_item("Generate webpages")
        try:
            cmd = [
                os.path.join(system.get('validation').jchronoss.src,
                             'tools/webview/webview_gen_all.sh'),
                "--new={}".format(os.path.join(outdir, "test_suite"))
            ]
            log.info('cmd: {}'.format(" ".join(cmd)))
            subprocess.check_call(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info("Browsing: {}".format(
                os.path.join(system.get('validation').jchronoss.src,
                             'tools/webview/webview/generated/main.html')))
        except (CalledProcessError, FileNotFoundError):
            pass

    log.print_item("Prepare the archive")
    # copy file before anonymizing them
    for root, _, files in os.walk(os.path.join(outdir, "test_suite")):
        for file in files:
            # TODO: save user-defined artifacts
            if file.endswith(('.json', '.xml', '.yml')):
                save_for_export(os.path.join(root, file))

    save_for_export(os.path.join(outdir, 'conf.yml'))
    # save_for_export(os.path.join(outdir, 'conf.env'))
    save_for_export(os.path.join(system.get('validation').jchronoss.src,
                                 "tools/webview"),
                    os.path.join(outdir, 'webview'))

    if system.get('validation').anonymize:
        log.print_item("Anonymizing data")
        anonymize_archive()

    log.print_item("Save user-defined artifacts")
    #log.warn('TODO user-defined artifact')

    log.print_item("Create the archive: {}".format(archive_name))

    with utils.cwd(outdir):
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


def __copy_file(src, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        shutil.copy(src, dest)
    except SameFileError:
        pass


def dup_another_build(build_dir, outdir):
    settings = None

    # First, load the whole config
    with open(os.path.join(build_dir, 'conf.yml'), 'r') as fh:
        d = Dict(yaml.load(fh, Loader=yaml.FullLoader))
        settings = system.Settings(d)

    # first, clear fields overridden by current run
    settings.validation.xmls = []
    settings.validation.output = outdir
    settings.validation.reused_build = build_dir

    # second, copy any xml/sh files to be reused
    for root, _, files, in os.walk(os.path.join(build_dir, "test_suite")):
        for f in files:
            if f in ('dbg-pcvs.yml', 'list_of_tests.xml', 'list_of_tests.sh'):
                src = os.path.join(root, f)
                dest = os.path.join(outdir,
                                    os.path.relpath(
                                        src,
                                        start=os.path.abspath(build_dir))
                                    )

                __copy_file(src, dest)

                if f == "list_of_tests.xml":
                    settings.validation.xmls.append(dest)

    # other files
    for f in ('conf.env'):
        src = os.path.join(build_dir, f)
        dest = os.path.join(outdir,
                            os.path.relpath(
                                src,
                                start=os.path.abspath(build_dir))
                            )
        if not os.path.isfile(src):
            continue

        __copy_file(src, dest)

    return settings
