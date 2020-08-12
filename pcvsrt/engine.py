import itertools
import os
from xml.sax.saxutils import escape
from pcvsrt import logs, descriptor
import pprint

sys_iterators = dict()


def unroll_criterion_decl(it_list):
    for name, it in sys_iterators.items():
        if isinstance(it['values'], list):
            if 'numeric' in it.keys() and it['numeric']:
                unrolled = descriptor.unroll_numeric_values(it['values'])
        else:
            unrolled = it
        sys_iterators[name]['values'] = list(set(unrolled))

    # unrolling is done twice to alleviate dep problem
    # This is tedious as it should be part of each iterator
    # unrolling to generate proper combinations :(
    for name, it in sys_iterators.items():
        if isinstance(it['values'], str):
            arg = it['values'].replace(' ', '')
            for dep_name in sys_iterators.keys():
                pass


def initialize(settings):
    # sanity checks
    assert (settings['validation']['profile']['runtime']['iterators'])
    runtime_iterators = settings['validation']['profile']['runtime']['iterators']
    criterion_iterators = settings['validation']['profile']['criterion']['iterators']
    it_to_remove = []
    logs.print_item("Prune undesired iterators from the run")
    for it in criterion_iterators.keys():
        if it not in runtime_iterators:
            logs.warn("Undeclared criterion as part of runtime: '{}' ".format(it))
        elif criterion_iterators[it]['values'] is None:
            logs.debug('No combination found for {}, removing from schedule'.format(it))
        else:
            continue
        it_to_remove.append(it)

    for k in criterion_iterators.keys():
        if k in it_to_remove:
            continue
    sys_iterators = {k: {**criterion_iterators[k], **runtime_iterators[k]} for k in criterion_iterators.keys() if k not in it_to_remove}
    logs.print_item("Expand possible iterator expressions")
    sys_iterators = unroll_criterion_decl(sys_iterators)


def __generate_test_line(**kwargs):
    keys = kwargs.keys()

    string = "<job><name>{}</name".format(kwargs['name'])
    string += "<deps>"
    if 'deps' in keys: string += "".join(["<dep>{}</dep>".format(d) for d in kwargs['deps']])
    string += "</deps>"
    string += "<command>{}</command>".format(escape(kwargs['command'], entities={
        "'": "&apos;",
        "\"": "&quot;"
    }))

    if 'time' in keys: string += "<time>{}</time>".format(kwargs['time'])
    if 'delta' in keys: string += "<delta>{}</delta>".format(kwargs['delta'])
    if 'resources' in keys: string += "<resources>{}</resources>".format(kwargs['n_res'])
    if 'extras' in keys: string += "<extras>{}</extras".format(kwargs['extras'])
    if 'postscript' in keys: string+= "<postCommand>{}</postCommand".format(kwargs['postscript'])
    return string
    

def process_desc(single_desc):
    global sys_iterators
    logs.info("processing {}".format(single_desc.name))
    return "<job><name>{}</name><command>echo 'toto'</command></job>".format(single_desc.name)
    if not single_desc.override_iterators():
        single_desc.iterators_set(sys_iterators)
    else:
        dict_it = single_desc.iterators
        for k in sys_iterators.keys():
            sys_values = sys_iterators[k]
            if k in dict_it.keys():
                # intersect sets
                dict_it[k]['values'] += sys_values
            else:
                dict_it[k]['values'] = sys_values
        single_desc.iterators_set(dict_it)
    
    return "<job>{}</job>".format(single_desc.serialize())

def finalize_file(path, package, content):
    fn = os.path.join(path, "list_of_tests.xml")
    with open(fn, 'w') as fh:
        fh.write("<jobSuite package='{}'>".format(package))
        fh.write(content)
        fh.write("</jobSuite>")
    return fn


def generate_combinations(self, *lists):
    for combination in list(itertools.product(*lists)):
        yield combination


if __name__ == '__main__':
    for i in generate_combinations(
            [1, 2, 3, 4],
            ['a', 'b', 'd'],
            [0.4, 2, 'test']):
        print(i)
