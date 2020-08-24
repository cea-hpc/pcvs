from addict import Dict
import itertools
import pprint
import re
from pcvsrt.context import settings
from xml.sax.saxutils import escape


def prepare_run_command(comb=None):
    args = []
    env = []
    for elt in comb:
        if elt in settings.runtime.iterators:
            n = Dict(settings.runtime.iterators[elt])
            value = n.aliases[comb[elt]] if comb[elt] in n.aliases else comb[elt]
            opt = str(n.option)+str(value)
            if 'before' in n.get('position', ""):
                opt = str(value)+str(n.option)

            if 'argument' in n.get('type', ""):
                args.append(opt)
            elif 'environment' in n.get('type', ""):
                env.append(opt)
        else:
            pass
    
    return " ".join(env + [settings.runtime.program, settings.runtime.args] + args)


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
        if i in langs and i in settings.compiler.commands:
            return i
    
    return 'cc'


def prepare_cmd_build_prefix(lang='cc', variants=[], comb=None):
    return " ".join([
        settings.compiler.commands.get(lang, 'echo'),
        " ".join(settings.compiler.variants[i].args for i in variants)
    ])


def stringify_combination(cur):
    assert(settings.criterion)
    sys = settings.criterion.iterators
    return "_".join([sys[n].subtitle+str(cur[n]).replace(" ", "-") for n in sorted(cur.keys())])


def gen_combinations(crits):
    lists = list()
    keys = list()
    for name, node in crits.items():
        lists.append(node['values'])
        keys.append(name)
    for combination in list(itertools.product(*lists)):
        yield {keys[i]: val for i, val in enumerate(combination)}


def convert_numeric_sequence(elt):
    assert(isinstance(elt, str))
    
    return elt

def xml_escape(s):
    return escape(s, entities={
        "'": "&apos;",
        "\"": "&quot;"
    })
