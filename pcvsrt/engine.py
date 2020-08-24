import os
import pprint

from pcvsrt import test, logs, helper
from pcvsrt.context import settings


def prepare_system_criterion(sys_it):
    final = sys_it
    for name, it in sys_it.items():
        if 'numeric' in it.keys() and it['numeric'] is True:
            if isinstance(it['values'], list):
                unrolled = [elt for elt in it['values'] if isinstance(elt, int)]
                unrolled += [helper.convert_numeric_sequence(elt) for elt in it['values'] if isinstance(elt, str)]
            else:
                unrolled = [it['values']]
        else:
            unrolled = [it['aliases'][i] for i in it['values']]
            
        final[name]['values'] = list(set(unrolled))
    
    # unrolling is done twice to alleviate dep problem
    # This is tedious as it should be part of each iterator
    # unrolling to generate proper combinations :(
    for name, it in sys_it.items():
        if isinstance(it['values'], str):
            arg = it['values'].replace(' ', '')
            for dep_name in sys_it.keys():
                pass
    return final

def initialize():
    # sanity checks
    assert (settings.runtime.iterators)
    runtime_iterators = settings.runtime.iterators
    criterion_iterators = settings.criterion.iterators
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
    sys_iterators = prepare_system_criterion(sys_iterators)

    # TODO: replace resource here by the one read from config
    test.TEDescriptor.init_system_wide(sys_iterators, 'n_node')


def finalize_file(path, package, content):
    fn = os.path.join(path, "list_of_tests.xml")
    with open(fn, 'w') as fh:
        fh.write("<jobSuite>")
        fh.write(content)
        fh.write("</jobSuite>")
    return fn
