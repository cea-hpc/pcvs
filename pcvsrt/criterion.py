import os
import itertools 

from pcvsrt.helpers import log, lowtest
from pcvsrt.helpers.system import sysTable

#######################################
###### COMBINATION MANAGEMENT #########
#######################################
class CombElement:
    def __init__(self, crit_desc, dict_comb):
        self._criterions = crit_desc
        self._combination = dict_comb

    def get(self, k, dflt=None):
        if k not in self._combination:
            return dlft
        return self._combination[k]

    def translate_to_str(self):
        c = self._criterions
        return "_".join([c[n].subtitle+str(self._combination[n]).replace(" ", "-") for n in sorted(self._combination.keys())])
    
    def translate_to_command(self):
        args = []
        envs = []
        params = []

        for k_elt, v_elt in self._combination.items():
            c = self._criterions[k_elt] 
            value = c.concretize_value(v_elt)
            if c.is_env():
                envs.append(value)
            elif c.is_local():
                params.append(value)
            else:
                args.append(value)
        return (envs, args, params)
        

class Combinations:
    @classmethod
    def register_sys_criterion(cls, system_criterion):
        cls.sys_iterators = system_criterion

    def __init__(self, dict_of_criterion):
        self._values = list()
        self._keys = list()
        self._dict = dict_of_criterion
        for name, node in dict_of_criterion.items():
                assert(isinstance(node, Criterion))
                assert(name == node.name)
                self._values.append(node.values)
                self._keys.append(node.name)

    def generate(self):
        for combination in list(itertools.product(*self._values)):
            yield CombElement(self._dict, {self._keys[i]: val for i, val in enumerate(combination)})


class Criterion:
    def __init__(self, name, description, local=False):
        self._name = name
        self._numeric = description.get('numeric', False) is True
        self._prefix = description.get('option', '')
        self._after = description.get('position', 'after') == 'after'
        self._alias = description.get('alias', {})
        self._is_env = description.get('type', 'argument') == 'environment'
        self._local = local

        self._str = description.get('subtitle', '')
        self._values = description.get('values', [])
        if isinstance(self._values, int) or isinstance(self._values, str):
            self._values = [self._values]
        self._values = set(self._values)

    def intersect(self, other):
        assert(isinstance(other, Criterion))
        assert(self._name == other._name)

        if self._values is None or other._values is None:
            self._values = None
        else:
            self._values = self._values.intersection(other._values)

    def is_empty(self):
        return self._values is not None and len(self._values) == 0
    
    def is_discarded(self):
        return self._values is None

    def is_local(self):
        return self._local

    def is_env(self):
        return self._is_env

    @staticmethod
    def __convert_str_to_int(str_elt):
        # TODO: write sequence conversion for numeric values
        return 0

    @property
    def values(self):
        return self._values

    @property
    def name(self):
        return self._name
    
    @property
    def subtitle(self):
        return self._str
    
    def concretize_value(self, val=''):
        # replace value with alias (if defined)
        val = str(self._alias[val] if val in self._alias else val)
        # put value before of after the defined prefix
        elt = self._prefix + val if self._after else val + self._prefix
        # return the elt. up to the caller to determine
        # if this should be added as an arg or an env
        # ==> is_env()
        return elt

    def aliased_value(self, val):
        return self._alias[val] if val in self._alias else val

    def expand_values(self):
        values = []
        if self._numeric is True:
            for v in self._values:
                if isinstance(v, int):
                    values.append(v)
                elif isinstance(v, str):
                    values.append(self.__convert_str_to_int(v))
                else:
                    raise TypeError("Only accept int or sequence (as string) as values for numeric iterators")
        else:
            values = self._values
        # now ensure values are unique
        self._values = list(set(values))

        # TODO: handle criterion dependency (ex: n_mpi: ['n_node * 2'])

def initialize_from_system():
    # sanity checks
    assert (sysTable.runtime.iterators)
    # raw YAML objects
    runtime_iterators = sysTable.runtime.iterators
    criterion_iterators = sysTable.criterion.iterators
    it_to_remove = []
    log.print_item("Prune undesired iterators from the run")

    # if a criterion defined in criterion.yaml but
    # not declared as part of a runtime, the criterion
    # should be silently discarded
    # here is the purpose
    for it in criterion_iterators.keys():
        if it not in runtime_iterators:
            log.warn("Undeclared criterion as part of runtime: '{}' ".format(it))
        elif criterion_iterators[it]['values'] is None:
            log.debug('No combination found for {}, removing from schedule'.format(it))
        else:
            continue
        it_to_remove.append(it)

    # register the new dict {criterion_name: Criterion object}
    # the criterion object gathers both information from runtime & criterion
    sysTable.criterion.iterators = {k: Criterion(k, {**runtime_iterators[k], **criterion_iterators[k]}) for k in criterion_iterators.keys() if k not in it_to_remove}

    # convert any sequence into valid range of integers for
    # numeric criterions
    log.print_item("Expand possible iterator expressions")
    for criterion in sysTable.criterion.iterators.values():
        criterion.expand_values()