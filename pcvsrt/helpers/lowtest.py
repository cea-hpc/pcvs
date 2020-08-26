import itertools
import os
import pprint
import re
from xml.sax.saxutils import escape

from addict import Dict

from pcvsrt.helpers.system import sysTable

#######################################
###### COMBINATION MANAGEMENT #########
#######################################
def __convert_comb(elt, n, comb):
    args = []
    env = []
    value = n.aliases[comb[elt]] if comb[elt] in n.aliases else comb[elt]
    opt = str(n.option)+str(value)

    if 'before' in n.get('position', ""):
        opt = str(value)+str(n.option)

    if 'environment' in n.get('type', ""):
        env.append(opt)
    else:
        args.append(opt)
    return (args, env)


def stringify_combination(cur):
    assert(sysTable.criterion)
    sys = sysTable.criterion.iterators
    return "_".join([sys[n].subtitle+str(cur[n]).replace(" ", "-") for n in sorted(cur.keys())])


def gen_combinations(crits):
    lists = list()
    keys = list()
    for name, node in crits.items():
        lists.append(node['values'])
        keys.append(name)
    for combination in list(itertools.product(*lists)):
        yield {keys[i]: val for i, val in enumerate(combination)}


# ######################################
# ####### COMMAND MANAGEMENT ###########
# ######################################
def prepare_run_command(comb=None, user_it=None, program="a.out"):
    args = []
    env = []
    params_env = []
    params = []
    for elt in comb:
        if elt in sysTable.runtime.iterators:
            a, e = __convert_comb(elt, Dict(sysTable.runtime.iterators[elt]), comb)
            args += a
            env += e
        elif elt in user_it:
            a, e = __convert_comb(elt, Dict(user_it[elt]), comb)
            params += a
            params_env += e
    return " ".join(
        env + params_env + 
        [sysTable.runtime.program, sysTable.runtime.args] +
        args +
        [program] +
        params)


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
        if i in langs and i in sysTable.compiler.commands:
            return i
    return 'cc'


def prepare_cmd_build_variants(variants=[], comb=None):
    return " ".join(sysTable.compiler.variants[i].args for i in variants)


def convert_numeric_sequence(elt):
    assert(isinstance(elt, str))
    return elt

def unfold_sequence(x, sys=None):
    return set(x) | sys

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