import base64
import itertools
import math
import os

from pcvs.helpers import log
from pcvs.helpers.exceptions import CommonException
from pcvs.helpers.system import MetaConfig
from pcvs.plugins import Plugin


class Combination:
    """A combination maps the actual concretization from multiple criterion.

    For a given set of criterion, a Combination carries, for each kind, its
    associated value in order to generate the appropriate test
    """

    def __init__(self, crit_desc, dict_comb):
        """Build a combination from two components:
        - the actual combination dict
        - the dict of criterions

        :param crit_desc: dict of criterions (=their full description)
            represented in the current combination.
        :type crit_desc: dict
        :param dict_comb: actual combination dict (k=criterion name, v=actual
            value)
        :type dict_comb: dict
        """
        self._criterions = crit_desc
        self._combination = dict_comb

    def get(self, k, dflt=None):
        """Retrieve the actual value for a given combination element
        :param k: value to retrieve
        :type k: str
        :param dflt: default value if k is not a valid key
        :type: object
        """
        if k not in self._combination:
            return dflt
        return self._combination[k]

    def items(self):
        """Get the combination dict.

        :return: the whole combination dict.
        :rtype: dict
        """
        return self._combination.items()

    def translate_to_str(self):
        """Translate the actual combination in a pretty-format string.
        This is mainly used to generate actual test names
        """
        c = self._criterions
        string = list()
        # each combination is built following: 'defined-prefix+value'
        for n in sorted(self._combination.keys()):
            if c[n].subtitle is None:
                continue
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

    def translate_to_dict(self):
        """Translate the combination into a dictionary.

        :return: configuration in the shape of a python dict
        :rtype: dict
        """
        return self._combination


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
        Note that here, the dict also contains program-based criterions
        :param dict_of_criterion: values to build the serie with
        :type dict_of_criterion: dict"""
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
            d = {self._keys[i]: val for i, val in enumerate(combination)}

            if not valid_combination(d):
                continue
            yield Combination(
                self._dict,
                d
            )


class Criterion:
    """A Criterion is the representation of a component each program
    (i.e. test binary) should be run against. A criterion comes with a range of
    possible values, each leading to a different test"""

    def __init__(self, name, description, local=False, numeric=False):
        """Initialize a criterion from its YAML/dict description
        :param name: name of the criterion
        :type name: str
        :param description: description of the criterion
        :type description: str
        :param local: True if the criterion is local, default to False
        :type local: bool
        :param numeric: True if the criterion is numeric, default to False
        :type: numeric: bool"""
        self._name = name
        if description is None:
            self._values = None
            return

        self._numeric = description.get('numeric', numeric) is True
        self._prefix = description.get('option', '')
        self._after = description.get('position', 'after') == 'after'
        self._alias = description.get('aliases', {})
        self._is_env = description.get('type', 'argument') == 'environment'
        # this should be only set by per-TE criterion definition
        self._local = local
        self._str = description.get('subtitle', None)
        self._values = description.get('values', [])
        if not isinstance(self._values, list):
            self._values = [self._values]

    # only allow overriding values (for now)

    def override(self, desc):
        """Replace the value of the criterion using a descriptor containing the
            said value

        :param desc: descriptor supposedly containing a ``value``entry
        :type desc: dict
        """
        if 'values' in desc:
            self._values = desc['values']

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
            self._values = set(self._values).intersection(other._values)

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
        """Get the ``value`` attribute of this criterion.

        :return: values of this criterion
        :rtype: list
        """
        return self._values

    def __len__(self):
        """Return the number of values this criterion holds.

        :return: the value list count
        :rtype: int
        """
        return len(self._values)

    @property
    def name(self):
        """Get the ``name`` attribute of this criterion.

        :return: name of this criterion
        :rtype: str
        """
        return self._name

    @property
    def subtitle(self):
        """Get the ``subtitle`` attribute of this criterion.

        :return: subtitle of this criterion
        :rtype: str
        """
        return self._str

    @property
    def numeric(self):
        """Get the ``numeric`` attribute of this criterion.

        :return: numeric of this criterion
        :rtype: str
        """
        return self._numeric

    def concretize_value(self, val=''):
        """Return the exact string mapping this criterion, according to the
        specification. (is it aliased ? should the option be put before/after
        the value?...)
        :param val: value to add with prefix
        :type val: str
        :return: values with aliases replaced
        :rtype: str"""
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
        a runtime to another
        :param val: string with aliases to be replaced"""
        return self._alias[val] if val in self._alias else val

    @staticmethod
    def __convert_sequence_to_list(node, s=-1, e=-1):
        """converts a sequence (as a string) to a valid list of values

        :param dic: dictionary to take the values from
        :type dic: dict
        :param s: start (can be overridden by ``from`` in ``dic``), defaults to
            -1
        :type s: int, optional
        :param e: end (can be overridden by ``to`` in ``dic``), defaults to -1
        :type e: int, optional
        :return: list of values
        :rtype: list
        """

        values = []

        # these must be integers
        def _convert_sequence_item_to_int(val):
            """helper to convert a string-formated number to a valid repr.

            :param val: the string-based number to convert
            :type val: str
            :raises CommonException.BadTokenError: val is not a number
            :return: the number
            :rtype: int() or float()
            """
            if not isinstance(val, int) or not isinstance(val, float):
                try:
                    n = float(val)
                    if n.is_integer():
                        return int(n)
                    else:
                        return n
                except ValueError:
                    raise CommonException.BadTokenError(val)

            else:
                return val

        start = _convert_sequence_item_to_int(node.get('from', s))
        end = _convert_sequence_item_to_int(node.get('to', e))
        of = _convert_sequence_item_to_int(node.get('of', 1))

        op = node.get('op', 'seq').lower()

        if op in ['seq', 'arithmetic', 'ari']:
            values = range(start, end+1, of)
        elif op in ['mul', 'geometric', 'geo']:
            if start == 0:
                values.append(0)
            elif of in [-1, 0, 1]:
                values.append(start ** of)
            else:
                cur = start
                while cur <= end:
                    values.append(cur)
                    cur *= of
        elif op in ['pow', 'powerof']:
            if of == 0:
                values.append()
            start = math.ceil(start**(1/of))
            end = math.floor(end**(1/of))
            for i in range(start, end+1):
                values.append(i**of)
        else:
            log.manager.warn("failure in Criterion sequence!")

        return values

    def expand_values(self):
        """Browse values for the current criterion and make it ready to
        generate combinations"""
        values = []

        if self._numeric is True:
            for v in self._values:
                if isinstance(v, dict):
                    values += self.__convert_sequence_to_list(v, s=0, e=100)
                elif isinstance(v, (int, float, str)):
                    values.append(v)
                else:
                    raise TypeError("Only accept int or sequence (as string)"
                                    " as values for numeric iterators")
        else:
            values = self._values
        # now ensure values are unique
        self._values = set(values)

        # TODO: handle criterion dependency (ex: n_mpi: ['n_node * 2'])


def initialize_from_system():
    """Initialise system-wide criterions

    TODO: Move this function elsewhere."""
    # sanity checks
    assert (MetaConfig.root.criterion.iterators)
    # raw YAML objects
    runtime_iterators = MetaConfig.root.runtime.iterators
    criterion_iterators = MetaConfig.root.criterion.iterators
    it_to_remove = []

    # if a criterion defined in criterion.yaml but
    # not declared as part of a runtime, the criterion
    # should be silently discarded
    # here is the purpose
    for it in criterion_iterators.keys():
        if it not in runtime_iterators:
            log.manager.warn("Undeclared criterion "
                             "as part of runtime: '{}' ".format(it))
        elif criterion_iterators[it]['values'] is None:
            log.manager.debug('No combination found for {},'
                              ' removing from schedule'.format(it))
        else:
            continue

        log.manager.info("Removing '{}'".format(it))
        it_to_remove.append(it)

    # register the new dict {criterion_name: Criterion object}
    # the criterion object gathers both information from runtime & criterion
    MetaConfig.root.set_internal('crit_obj', {k: Criterion(
        k, {**runtime_iterators[k], **criterion_iterators[k]}) for k in criterion_iterators.keys() if k not in it_to_remove})

    # convert any sequence into valid range of integers for

    # numeric criterions
    comb_cnt = 1
    for criterion in MetaConfig.root.get_internal('crit_obj').values():
        criterion.expand_values()
        comb_cnt *= len(criterion)
    MetaConfig.root.set_internal("comb_cnt", comb_cnt)


first = True


def valid_combination(dic):
    """Check if dict is a valid criterion combination .

    :param dic: dict to check
    :type dic: dict
    :return: True if dic is a valid combination
    :rtype: bool
    """
    global first
    rt = MetaConfig.root.runtime
    val = MetaConfig.root.validation
    pCollection = MetaConfig.root.get_internal('pColl')

    if first and rt.plugin:
        first = not first

        rt.pluginfile = os.path.join(val.buildcache, "rt-plugin.py")
        with open(rt.pluginfile, 'w') as fh:
            fh.write(base64.b64decode(rt.plugin).decode('ascii'))

        pCollection.register_plugin_by_file(rt.pluginfile, activate=True)

    ret = pCollection.invoke_plugins(Plugin.Step.TEST_EVAL,
                                     config=MetaConfig.root,
                                     combination=dic)

    # by default, no plugin = always true
    if ret is None:
        ret = True

    return ret
