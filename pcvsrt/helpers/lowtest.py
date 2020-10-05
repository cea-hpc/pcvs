import itertools
import os
import pprint
import re
import importlib
import base64
from xml.sax.saxutils import escape
from addict import Dict

from pcvsrt.helpers import system, pm


# ######################################
# ####### COMMAND MANAGEMENT ###########
# ######################################
def detect_source_lang(array_of_files):
    langs = Dict()
    for f in array_of_files:
        if re.match(r'\.(h|H|i|I|s|S|c|c90|c99|c11)$', f):
            langs.cc = True
        elif re.match(r'\.C|cc|cxx|cpp|c\+\+$', f):
            langs.cxx = True
        elif re.match(r'\.(f|F)(77)$', f):
            langs.f77 = True
        elif re.match(r'\.(f|F)90$', f):
            langs.f90 = True
        elif re.match(r'\.(f|F)95$', f):
            langs.f95 = True
        elif re.match(r'\.(f|F)(20)*03$', f):
            langs.f03 = True
        elif re.match(r'\.(f|F)(20)*08$', f):
            langs.f08 = True
        elif re.match(r'\.(f|F)$', f):
            langs.fc = True

    # now return the first valid language, according to settings
    # order matters: if sources contains multiple languages, the first
    # appearing in this list will be considered as the main language
    for i in ['f08', 'f03', 'f95', 'f90', 'f77', 'fc','cxx', 'cc']:
        if i in langs and i in system.get('compiler').commands:
            return i
    return 'cc'


def prepare_cmd_build_variants(variants=[], comb=None):
    return " ".join(system.get('compiler').variants[i].args for i in variants)


def xml_escape(s):
    return escape(s, entities={
        "'": "&apos;",
        "\"": "&quot;"
    })


def xml_setif(elt, k, tag=None):
    if tag is None:
        tag = k
    if k in elt.keys() and elt[k] is not None:
        if isinstance(elt[k], list):
            return "".join(["<"+tag+">"+xml_escape(str(i))+"</"+tag+">" for i in elt[k]])
        else:
            return "<"+tag+">"+xml_escape(str(elt[k]))+"</"+tag+">"
    else:
        return ""


def handle_job_deps(deps_node, pkg_prefix):
    deps = list()
    if 'depends_on' in deps_node:
        for name, values in deps_node['depends_on'].items():
            if name == 'test':
                for d in values:
                    deps.append(d if '.' in d else ".".join([pkg_prefix, d]))
            else:
                deps += [d for d in pm.identify_manager({name: values})]
    return deps

first = True
runtime_filter = None
def valid_combination(dic):
    global first, runtime_filter
    rt = system.get('runtime')
    val = system.get('validation')
    if first is True and rt.plugin:
        first = False
        rt.pluginfile =  os.path.join(val.output, "cache/rt-plugin.py")
        with open(rt.pluginfile, 'w') as fh:
            fh.write(base64.b64decode(rt.plugin).decode('ascii'))
        
        spec = importlib.util.spec_from_file_location("pcvsrt.user-rt-plugin",
                                                      rt.pluginfile)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        if hasattr(mod, 'check_valid_combination') and \
           callable(mod.check_valid_combination):
            runtime_filter = mod.check_valid_combination
            # add here any relevant information to be accessed by modules
            mod.sys_nodes = system.get('machine').nodes
            mod.sys_cores_per_node = system.get('machine').cores_per_node

    if runtime_filter:
        return runtime_filter(dic)
    else:
        return True

def max_number_of_combinations():
    product = 1
    c = system.get('criterion').iterators
    for k in c:
        product *= len(c[k]['values'])
    return product