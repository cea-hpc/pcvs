import itertools
from pcvsrt import logs
import pprint

sys_iterators = dict()

def unroll_numeric_values(array):
    for entry in array:
        if not isinstance(entry, str):
            logs.warn("Unable to deal with non-scalar iterator values; skip {}".format(entry))
        else:
            logs.warn("TODO unrooling numeric values")
    return array


def unroll_iterators(it_list):
    for name, it in sys_iterators.items():
        if isinstance(it['values'], list):
            if 'numeric' in it.keys() and it['numeric']:
                unrolled = unroll_numeric_values(it['values'])
        else:
            unrolled = it
        sys_iterators[name]['values'] = unrolled

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
    sys_iterators = unroll_iterators(sys_iterators)


def process(single_te):
    logs.info("processing {}".format(single_te.name))
    pass


def generate_combinations(self, *lists):
    for combination in list(itertools.product(*lists)):
        yield combination


if __name__ == '__main__':
    for i in generate_combinations(
            [1, 2, 3, 4],
            ['a', 'b', 'd'],
            [0.4, 2, 'test']):
        print(i)
