import fileinput
import os
import pprint
import shutil
import subprocess
import time
from shutil import SameFileError
from subprocess import CalledProcessError

import yaml
from addict import Dict

from pcvs import (NAME_BUILD_CONF_FN, NAME_BUILD_RESDIR, NAME_BUILDFILE,
                  NAME_BUILDIR, NAME_SRCDIR)
from pcvs.backend import bank as pvBank
from pcvs.helpers import criterion, log, utils
from pcvs.helpers.exceptions import RunException
from pcvs.helpers.system import MetaConfig
from pcvs.orchestration import Orchestrator
from pcvs.testing.tedesc import TEDescriptor
from pcvs.testing.testfile import TestFile


def print_progbar_walker(elt):
    if elt is None:
        return None
    return "["+elt[0]+"] " + (elt[1] if elt[1] else "")

def str_dict_as_envvar(d):
    return "\n".join(["{}='{}'".format(i, d[i]) for i in sorted(d.keys())])


def copy_file(src, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        shutil.copy(src, dest)
    except SameFileError:
        pass

def process_main_workflow(the_session=None):
    global_config = MetaConfig.root
    valcfg = global_config.validation

    log.manager.print_banner()
    log.manager.print_header("Prepare Environment")
    # prepare PCVS and third-party tools
    prepare()

    log.manager.print_header("Process benchmarks")
    if valcfg.reused_build is not None:
        log.manager.print_section("Reusing previously generated inputs")
        log.manager.print_section("Duplicated from {}".format(os.path.abspath(valcfg.reused_build)))
    else:
        start = time.time()
        process()
        end = time.time()
        log.manager.print_section(
                "===> Processing done in {:<.3f} sec(s)".format(end-start))
    
    log.manager.print_header("Validation Start")
    run()

    log.manager.print_header("Finalization")
    # post-actions to build the archive, post-process the webview...
    terminate()

    bank_token = valcfg.target_bank
    if bank_token is not None:
        bank = pvBank.Bank(token=bank_token)
        pref_proj = bank.preferred_proj
        if bank.exists():
            log.manager.print_item("Upload to the bank '{}{}'".format(
                    bank.name.upper(),
                    " (@{})".format(pref_proj) if pref_proj else ""
                ))
            bank.connect_repository()
            bank.save_from_buildir(
                None,
                os.path.join(valcfg.output)
            )


def __print_summary():
    cfg = MetaConfig.root.validation
    log.manager.print_section("Summary:")
    log.manager.print_item("Loaded profile: '{}'".format(cfg.pf_name))
    log.manager.print_item("Built into: {}".format(cfg.output))
    log.manager.print_item("Verbosity: {}".format(
        log.manager.get_verbosity_str().capitalize()))
    log.manager.print_item("User directories:")
    width = max([len(i) for i in cfg.dirs])
    for k, v in cfg.dirs.items():
        log.manager.print_item("{:<{width}}: {:<{width}}".format(
            k.upper(),
            v,
            width=width),
            depth=2)

def __check_defined_program_validity():
    # exhaustive list of user-defined program to exist before starting:
    utils.check_valid_program(MetaConfig.root.machine.job_manager.allocate.program)
    utils.check_valid_program(MetaConfig.root.machine.job_manager.allocate.wrapper)
    utils.check_valid_program(MetaConfig.root.machine.job_manager.run.program)
    utils.check_valid_program(MetaConfig.root.machine.job_manager.run.wrapper)
    utils.check_valid_program(MetaConfig.root.machine.job_manager.batch.program)
    utils.check_valid_program(MetaConfig.root.machine.job_manager.batch.wrapper)
    return
    # TODO: need to handle package_manager commands to process below
    # maybe a dummy testfile should be used
    utils.check_valid_program(MetaConfig.root.compiler.commands.cc)
    utils.check_valid_program(MetaConfig.root.compiler.commands.cxx)
    utils.check_valid_program(MetaConfig.root.compiler.commands.fc)
    utils.check_valid_program(MetaConfig.root.compiler.commands.f77)
    utils.check_valid_program(MetaConfig.root.compiler.commands.f90)
    utils.check_valid_program(MetaConfig.root.runtime.program)


def prepare():
    log.manager.print_section("Prepare environment")
    log.manager.print_item("Date: {}".format(
        MetaConfig.root.validation.datetime.strftime("%c")))
    valcfg = MetaConfig.root.validation

    log.manager.print_item("Check whether build directory is valid")
    buildir = os.path.join(valcfg.output, "test_suite")
    if not os.path.exists(buildir):
        os.makedirs(buildir)
    # if a previous build exists
    if valcfg.reused_build is None:
        log.manager.print_item("Cleaning up {}".format(buildir), depth=2)
        utils.create_or_clean_path(buildir)
    utils.create_or_clean_path(os.path.join(
        valcfg.output, NAME_BUILDFILE))
    utils.create_or_clean_path(os.path.join(valcfg.output, 'webview'), dir=True)
    utils.create_or_clean_path(os.path.join(valcfg.output, NAME_BUILD_CONF_FN))
    utils.create_or_clean_path(os.path.join(valcfg.output, 'conf.env'))
    utils.create_or_clean_path(os.path.join(valcfg.output, 'save_for_export'), dir=True)
    utils.create_or_clean_path(os.path.join(valcfg.output, NAME_BUILD_RESDIR), dir=True)
    utils.create_or_clean_path(valcfg.buildcache)
    
    log.manager.print_item("Create subdirs for each provided directories")
    os.makedirs(buildir, exist_ok=True)
    for label in valcfg.dirs.keys():
        os.makedirs(os.path.join(buildir, label), exist_ok=True)
    open(os.path.join(valcfg.output, NAME_BUILDFILE), 'w').close()

    #log.manager.print_section("Build third-party tools")
    #__build_tools()

    log.manager.print_section("Ensure user-defined programs exist")
    __check_defined_program_validity()

    log.manager.print_section("Load and initialize validation criterions")
    criterion.initialize_from_system()
    # Pick on criterion used as 'resources' by JCHRONOSS
    # this is set by the run configuration
    # TODO: replace resource here by the one read from config
    TEDescriptor.init_system_wide('n_node')

    MetaConfig.root.set_internal('orchestrator', Orchestrator())

def find_files_to_process(path_dict):
    setup_files = list()
    yaml_files = list()

    # discovery may take a while with some systems
    log.manager.print_item("PCVS-related file detection")
    # iterate over user directories
    for label, path in path_dict.items():
        # for each, walk through the tree
        for root, dirs, list_files in os.walk(path):
            last_dir = os.path.basename(root)
            # if the current dir is a 'special' one, discard
            if last_dir in [NAME_SRCDIR, NAME_BUILDIR, "build_scripts"]:
                log.manager.debug("skip {}".format(root))
                # set dirs to null, avoiding os.wal() to go further in that dir
                dirs[:] = []
                continue
            # otherwise, save the file
            for f in list_files:
                # [1:] to remove extra '/'
                subtree = os.path.relpath(root, path)
                if subtree == ".":
                    subtree = None
                if 'pcvs.setup' == f:
                    setup_files.append((label, subtree, f))
                elif 'pcvs.yml' == f or 'pcvs.yml.in' == f:
                    yaml_files.append((label, subtree, f))
    return (setup_files, yaml_files)


def process():
    log.manager.print_section("Load from filesystem")
    setup_files, yaml_files = find_files_to_process(
        MetaConfig.root.validation.dirs)

    log.manager.debug("Found setup files: {}".format(pprint.pformat(setup_files)))
    log.manager.debug("Found static files: {}".format(pprint.pformat(yaml_files)))

    errors = []
    errors += process_dyn_setup_scripts(setup_files)
    errors += process_static_yaml_files(yaml_files)

    if len(errors):
        raise RunException.TestUnfoldError(errors)


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

def process_dyn_setup_scripts(setup_files):
    err = []
    log.manager.print_item("Convert configuation to Shell variables")
    env = os.environ.copy()
    env.update(build_env_from_configuration(MetaConfig.root))

    env_script = os.path.join(MetaConfig.root.validation.output, 'conf.env')
    with open(env_script, 'w') as fh:
        fh.write(str_dict_as_envvar(env))
        fh.close()

    log.manager.print_item("Manage dynamic files (scripts)")
    with log.progbar(setup_files, print_func=print_progbar_walker) as itbar:
        for label, subprefix, fname in itbar:
            log.manager.info("process {} ({})".format(subprefix, label))
            base_src, cur_src, base_build, cur_build = utils.generate_local_variables(
                label, subprefix)

            ## prepre to exec pcvs.setup script
            # 1. setup the env
            env['pcvs_src'] = base_src
            env['pcvs_testbuild'] = base_build
            te_node = None
            out_file = None

            if not os.path.isdir(cur_build):
                os.makedirs(cur_build)
            
            f = os.path.join(cur_src, fname)

            # Run the script
            try:
                fds = subprocess.Popen([f, subprefix], env=env,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
                fdout, fderr = fds.communicate()

                if fds.returncode != 0:
                    err.append((f, fderr.decode('utf-8')))
                    log.manager.info("{}: {}".format(f, fderr.decode('utf-8')))
                    continue

                # flush the output to $BUILD/pcvs.yml
                out_file = os.path.join(cur_build, 'pcvs.yml')
                with open(out_file, 'w') as fh:
                    fh.write(fdout.decode('utf-8'))
                te_node = test.load_yaml_file(
                    out_file, base_src, base_build, subprefix)
            except CalledProcessError:
                pass

            # If the script did not generate any output, skip
            if te_node is None:  # empty file
                continue

            # Now create the file handler
            obj = TestFile(file_in=out_file,
                path_out=cur_build,
                data=te_node,
                label=label,
                prefix=subprefix
            )
            obj.process()
            obj.flush_sh_file()
    return err

def process_static_yaml_files(yaml_files):
    err = []
    log.manager.print_item("Process static test files")
    with log.progbar(yaml_files, print_func=print_progbar_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            _, cur_src, _, cur_build = utils.generate_local_variables(
                label, subprefix)
            if not os.path.isdir(cur_build):
                os.makedirs(cur_build)
            f = os.path.join(cur_src, fname)
            
            try:
                obj = TestFile(file_in=f,
                    path_out=cur_build,
                    label=label,
                    prefix=subprefix
                )
                obj.process()
                obj.flush_sh_file()
            except (yaml.YAMLError, CalledProcessError) as e:
                # log errors to be printed all at once
                err.append((f, e.output))
                log.manager.info("{}: {}".format(f, e.output))
                continue
            except Exception as e:
                err.append((f, e))
                log.manager.info("Failed to read {}: ".format(f), "{}".format(e))
    return err


def run():
    __print_summary()
    log.manager.print_item("Save Configurations into {}".format(
        MetaConfig.root.validation.output))

    conf_file = os.path.join(MetaConfig.root.validation.output, NAME_BUILD_CONF_FN)
    with open(conf_file, 'w') as conf_fh:
        yaml.safe_dump(MetaConfig.root.dump_for_export(), conf_fh, default_flow_style=None)

    log.manager.print_section("Run the Orchestrator")
    MetaConfig.root.get_internal('orchestrator').run()

def anonymize_archive():
    config = MetaConfig.root.validation
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
    config = MetaConfig.root.validation
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
            raise RunException.UnclassifiableError("{}".format(f))
    except FileNotFoundError as e:
        raise RunException.NotFoundError(e, f)


def terminate():
    archive_name = "pcvsrun_{}.tar.gz".format(
        MetaConfig.root.validation.datetime.strftime('%Y%m%d%H%M%S'))
    outdir = MetaConfig.root.validation.output
    
    log.manager.print_section("Exporting results")
    
    log.manager.print_item("Prepare the archive")
    #TODO: copy declared artifacts
    # copy file before anonymizing them
    #for root, _, files in os.walk(os.path.join(outdir, "test_suite")):
    #    for file in files:
    #        # TODO: save user-defined artifacts
    #        if file.endswith(('.json', '.xml', '.yml')):
    #            save_for_export(os.path.join(root, file))

    save_for_export(os.path.join(outdir, NAME_BUILD_RESDIR))
    save_for_export(os.path.join(outdir, NAME_BUILD_CONF_FN))
    
    if MetaConfig.root.validation.anonymize:
        log.manager.print_item("Anonymizing data")
        anonymize_archive()

    log.manager.print_item("Save user-defined artifacts")
    #log.manager.warn('TODO user-defined artifact')

    log.manager.print_item("Create the archive: {}".format(archive_name))

    with utils.cwd(outdir):
        cmd = [
            "tar",
            "czf",
            "{}".format(archive_name),
            "save_for_export"
        ]
        try:
            log.manager.info('cmd: {}'.format(" ".join(cmd)))
            subprocess.check_call(cmd)
        except CalledProcessError as e:
            raise RunException.ProgramError(e, cmd)

    return archive_name

def dup_another_build(build_dir, outdir):
    global_config = None

    # First, load the whole config
    with open(os.path.join(build_dir, NAME_BUILD_CONF_FN), 'r') as fh:
        d = Dict(yaml.safe_load(fh))
        global_config = MetaConfig(d)

    # first, clear fields overridden by current run
    global_config.validation.output = outdir
    global_config.validation.reused_build = build_dir
    global_config.validation.buildcache = os.path.join(outdir, 'cache')

    # second, copy any xml/sh files to be reused
    for root, _, files, in os.walk(os.path.join(build_dir, "test_suite")):
        for f in files:
            if f in ('dbg-pcvs.yml', 'list_of_tests.sh'):
                src = os.path.join(root, f)
                dest = os.path.join(outdir,
                                    os.path.relpath(
                                        src,
                                        start=os.path.abspath(build_dir))
                                    )

                copy_file(src, dest)

                if f == "list_of_tests.xml":
                    global_config.get('validation').xmls.append(dest)

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

        copy_file(src, dest)

    return global_config
