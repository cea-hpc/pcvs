import base64
import importlib
import os
import pprint
import re
from xml.sax.saxutils import escape

from addict import Dict

from pcvs.helpers import package_manager, system


# ######################################
# ##### TEST: INPUT TRANSFORMATION #####
# ######################################
def detect_source_lang(array_of_files):
    detect = list()
    for f in array_of_files:
        if re.search(r'\.(h|H|i|I|s|S|c|c90|c99|c11)$', f):
            detect.append('cc')
        elif re.search(r'\.C|cc|cxx|cpp|c\+\+$', f):
            detect.append('cxx')
        elif re.search(r'\.(f|F)(77)$', f):
            detect.append('f77')
        elif re.search(r'\.(f|F)90$', f):
            detect.append('f90')
        elif re.search(r'\.(f|F)95$', f):
            detect.append('f95')
        elif re.search(r'\.(f|F)(20)*03$', f):
            detect.append('f03')
        elif re.search(r'\.(f|F)(20)*08$', f):
            detect.append('f08')
        elif re.search(r'\.(f|F)$', f):
            detect.append('fc')

    # now return the first valid language, according to settings
    # order matters: if sources contains multiple languages, the first
    # appearing in this list will be considered as the main language
    for i in ['f08', 'f03', 'f95', 'f90', 'f77', 'fc', 'cxx', 'cc']:
        if i in detect and i in system.get('compiler').commands:
            return i
    return 'cc'


def prepare_cmd_build_variants(variants=[], comb=None):
    return " ".join(system.get('compiler').variants[i].args for i in variants)


def handle_job_deps(deps_node, pkg_prefix):
    deps = list()
    if 'depends_on' in deps_node:
        for name, values in deps_node['depends_on'].items():
            if name == 'test':
                for d in values:
                    deps.append(d if '/' in d else "/".join([pkg_prefix, d]))
            else:
                deps += [d for d in package_manager.identify({name: values})]
    return deps


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
