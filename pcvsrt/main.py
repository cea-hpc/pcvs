import os
from pcvsrt.utils import logs
from pcvsrt import config, profile

run_settings = {}

def __print_summary():
    logs.print_section("Validation details")

def __build_third_party():
    logs.print_section("Build third-party tools")
    logs.print_item("job orchestrator (JCHRONOSS)")
    logs.print_item("Web-based reporting tool")

def prepare(settings):
    global run_settings

    run_settings = settings
    pf = profile.Profile()
    run_settings['profile'] = pf.load(settings['pfname'])
    __print_summary()
    __build_third_party()


def load_benchmarks(dirpaths):
    logs.print_section("Load Benchmarks")
    list_of_dirs = map(lambda x: os.path.abspath(x), dirpaths)
    yaml_files = []
    setup_files = []

    for path in list_of_dirs:
        for root, dirs, files in os.walk(path):
            if '.pcvsrt' in root: # ignore pcvs-rt conf subdirs
                continue
            # save static YAML files (including *.in)
            yaml_files += [os.path.join(root, f) for f in files if 'pcvs.yml' in f]
            # save scripts
            setup_files += [os.path.join(root, f) for f in files if f == 'pcvs.setup']
    pass


def run():
    pass


def terminate():
    pass