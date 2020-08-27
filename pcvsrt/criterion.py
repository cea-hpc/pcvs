import itertools

from pcvsrt.helpers import log
from pcvsrt.helpers.system import sysTable


class Combination:
    """A combination maps the actual concretization from multiple criterion.

    For a given set of criterion, a Combination carries, for each kind, its
    associated value in order to generate the appropriate test
    """
    def __init__(self, crit_desc, dict_comb):
        """Build a combination from two components:
        - the actual combination dict (k=criterion name, v=actual value)
        - the dict of criterions (=their full description) represented in the
          current combination.
        """
        self._criterions = crit_desc
        self._combination = dict_comb

    def get(self, k, dflt=None):
        """Retrieve the actual value for a given combination element"""
        if k not in self._combination:
            return dflt
        return self._combination[k]

    def translate_to_str(self):
        """Translate the actual combination in a pretty-format string.
        This is mainly used to generate actual test names
        """
        c = self._criterions
        string = list()
        # each combination is built following: 'defined-prefix+value'
        for n in sorted(self._combination.keys()):
            string.append(c[n].subtitle +
                          str(self._combination[n]).replace(" ", "-"))
        return "_".join(string)

    def translate_to_command(self):
        """Translate the actual combination is tuple of three elements, based
        on the representation of each criterion in the test semantic. It builds
        tokens to provide to properly build the test command. It can
        either be:
        1. an environment variable to export before the test to run (gathering
           system-scope and program-scope elements)
        2. a runtime argument
        3. a program-level argument (through custom-made iterators)
        """
        args = []
        envs = []
        params = []

        # for each elt, where k is the criterion name, v is the actual value
        for k_elt, v_elt in self._combination.items():
            c = self._criterions[k_elt]
            # concretize_value() gathers both criterion label & value according
            # to specs (before, after, aliasing...)
            value = c.concretize_value(v_elt)

            if c.is_env():
                envs.append(value)
            elif c.is_local():
                params.append(value)
            else:
                args.append(value)
        return (envs, args, params)


class Serie:
    """A serie ties a test expression (TEDescriptor) to the possible values
    which can be taken for each criterion to build test sets.
    A serie can be seen as the Combination generator for a given TEDescriptor
    """
    @classmethod
    def register_sys_criterion(cls, system_criterion):
        """copy/inherit the system-defined criterion (shortcut to global config)
        """
        cls.sys_iterators = system_criterion

    def __init__(self, dict_of_criterion):
        """Build a serie, by extracting the list of values.
        Note that here, the dict also contains program-based criterions"""
        self._values = list()
        self._keys = list()
        # this has to be saved, need to be forwarded to each combination
        self._dict = dict_of_criterion
        for name, node in dict_of_criterion.items():
            assert(isinstance(node, Criterion))
            assert(name == node.name)
            self._values.append(node.values)
            self._keys.append(node.name)

    def generate(self):
        """Generator to build each combination"""
        for combination in list(itertools.product(*self._values)):
            yield Combination(
                self._dict, 
                {self._keys[i]: val for i, val in enumerate(combination)}
            )


class Criterion:
    """A Criterion is the representation of a component each program
    (i.e. test binary) should be run against. A criterion comes with a range of
    possible values, each leading to a different test"""
    def __init__(self, name, description, local=False):
        """Initialize a criterion from its YAML/dict description"""
        self._name = name
        self._numeric = description.get('numeric', False) is True
        self._prefix = description.get('option', '')
        self._after = description.get('position', 'after') == 'after'
        self._alias = description.get('alias', {})
        self._is_env = description.get('type', 'argument') == 'environment'
        # this should be only set by per-TE criterion definition
        self._local = local

        self._str = description.get('subtitle', '')
        self._values = description.get('values', [])

        # convert any scalar value to a set()
        if isinstance(self._values, int) or isinstance(self._values, str):
            self._values = [self._values]

        # values are unique for a single criterion
        self._values = set(self._values)

    def intersect(self, other):
        """Update the calling Criterion with the interesection of the current
        range of possible values with the one given as a parameters.

        This is used to refine overriden per-TE criterion according to 
        system-wide's"""
        assert(isinstance(other, Criterion))
        assert(self._name == other._name)

        # None is special value meaning, discard this criterion because
        # irrelevant
        if self._values is None or other._values is None:
            self._values = None
        else:
            self._values = self._values.intersection(other._values)

    def is_empty(self):
        """Is the current set of values empty 
        May lead to errors, as it may indicates no common values has been
        found between user and system specifications"""
        return self._values is not None and len(self._values) == 0
    
    def is_discarded(self):
        """Should this criterion be ignored from the current TE generaiton ?"""
        return self._values is None

    def is_local(self):
        """Is the criterion local ? (program-scoped)"""
        return self._local

    def is_env(self):
        """Is this criterion targeting a component used as an env var ?"""
        return self._is_env

    @staticmethod
    def __convert_str_to_int(str_elt):
        """Convert a sequence (as a string) into a valid range of values.
        
        This is used to build criterion numeric-only possible values"""
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
        """Return the exact string mapping this criterion, according to the
        specification. (is it aliased ? should the option be put before/after
        the value?...)"""
        # replace value with alias (if defined)
        val = str(self.aliased_value(val))
        # put value before of after the defined prefix
        elt = self._prefix + val if self._after else val + self._prefix
        # return the elt. up to the caller to determine
        # if this should be added as an arg or an env
        # ==> is_env()
        return elt

    def aliased_value(self, val):
        """Check if the given value has an alias for the current criterion.
        An alias is the value replacement to use instead of the one defined by
        test configuration. This allows to split test logic from runtime
        semantics.

        For instance, TEs manipulate 'ib' as a value to depict the 'infiniband'
        network layer. But once the test has to be built, the term will change
        depending on the runtime carrying it, the value may be different from
        a runtime to another"""
        return self._alias[val] if val in self._alias else val

    def expand_values(self):
        """Browse values for the current criterion and make it ready to
        generate combinations"""
        values = []
        if self._numeric is True:
            for v in self._values:
                if isinstance(v, int):
                    values.append(v)
                elif isinstance(v, str):
                    values.append(self.__convert_str_to_int(v))
                else:
                    raise TypeError("Only accept int or sequence (as string)"
                                    " as values for numeric iterators")
        else:
            values = self._values
        # now ensure values are unique
        self._values = list(set(values))

        # TODO: handle criterion dependency (ex: n_mpi: ['n_node * 2'])


def initialize_from_system():
    """Initialise system-wide criterions

    TODO: Move this function elsewhere."""
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
            log.warn("Undeclared criterion "
                     "as part of runtime: '{}' ".format(it))
        elif criterion_iterators[it]['values'] is None:
            log.debug('No combination found for {},'
                      ' removing from schedule'.format(it))
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