"""
Criterion Modules:

- Criterion:
    A criterion represent a test parameter (command line argument or environment variables)
    and the different values that the parameter will takes when running the test. (-n=1, -n=2, ...)
    Their can be multiples criterions per tests. (-n=[1, 8], -N=[1, 8])

- Combinations:
    One or multiples criterions are expanded into combinations.
    One combination contain one value for each criterion such as (-n=1, -N=2, ...).
    For each combination their will be a run of the test with the argument at the value of the combination.
    A Combination may be valid or invalid. (-n=1 & -N=2 is an invalid combination).
    Combination are vallidated by plugins.

- Series:
    A Series (of combination), represent all the valid Combinations that the test will be run with.
"""

import itertools
import math
import os
from typing import Any
from typing import ItemsView
from typing import Iterable

from typing_extensions import Self

from pcvs import io
from pcvs.backend.metaconfig import GlobalConfig
from pcvs.helpers.exceptions import CommonException
from pcvs.plugins import Collection
from pcvs.plugins import Plugin


class Criterion:
    """
    A Criterion is the representation of a component (i.e. parameter)
    each program (i.e. test binary) should be run against.
    A criterion comes with a range of possible values, each leading to a different test.
    """

    def __init__(
        self, name: str, description: dict[str, Any], local: bool = False, numeric: bool = False
    ):
        """
        Initialize a criterion from its YAML/dict description.

        :param name: name of the criterion (eg: n_mpi)
        :param description: description of the criterion from configuration, include:

            - numeric: :py:obj:`bool`, is the criterion numeric
            - option: :py:obj:`str`, what is the option of the criterion (eg: -N)
            - position: :py:obj:`str`, 'after' or 'before' is the criterion option before or after it's value
            - aliases: :py:obj:`list[str]`, aliases names for the criterion
            - type: :py:obj:`str`, 'argument' or 'environment'
            - local: :py:obj:`bool`, if the criterion a parameter,
                should the criterion be a parameter of the test or a parameter of the wrapper
            - subtitle: :py:obj:`str`, the str that will be used with the current value to name the test

        :param local: True if the criterion is a parameter on the test binary,
                      False if it is a parameter to the wrapper,
                      default to False, is override by local in description.
        :param numeric: True if the criterion is numeric, default to False
        """
        self._name = name
        self._input_values: list[int | float | str | dict[str, Any]] | None
        self._values: set[int | float | str] | None

        self._numeric: bool = description.get("numeric", numeric)
        self._prefix: str = description.get("option", "")
        self._after: bool = description.get("position", "after") == "after"
        self._alias: dict[str, str] = description.get("aliases", {})
        self._is_env: bool = description.get("type", "argument") == "environment"
        # this should be only set by per-TE criterion definition
        self._local: bool = description.get("local", local)
        self._subtitle: str = description.get("subtitle", name)
        # Sanity check
        self._input_values = self.__sanitize_values(description.get("values", []))
        self._values = None
        self._expanded: bool = False

    def __sanitize_values(
        self,
        input_values: (
            list[int | float | str | dict[str, Any]] | dict[str, Any] | int | float | str | None
        ),
    ) -> list[int | float | str | dict[str, Any]] | None:
        """
        Check for any inconsistent values in the current Criterion.

        Currently, only scalar items or dict (=> sequence) are allowed.
        Will raise an exception in case of inconsistency (Maybe this should be
        managed in another way through the error handling)

        :param input_values: The values the will be parsed to generate this criterion value list.
        :raises CommonException.UnclassifiableError: When there is an error in the semantic of the provided yaml file.
        :return: The expanded value list.

        # noqa: DAR401
        # noqa: DAR402
        """
        if input_values is None:
            return None
        if isinstance(input_values, (int, float, str, dict)):
            input_values = [input_values]
        if isinstance(input_values, list):
            for v in input_values:
                if not isinstance(v, (int, float, str, dict)):
                    raise CommonException.UnclassifiableError(
                        reason="Criterion: list elements should be an int, float, str or dict.",
                        dbg_info={"element": v},
                    )
                if isinstance(v, dict):
                    for key in v.keys():
                        if key not in ["op", "of", "from", "to"]:
                            raise CommonException.UnclassifiableError(
                                reason="Criterion: invlide sequence operation.",
                                dbg_info={"element": str(v)},
                            )
        else:
            raise CommonException.UnclassifiableError(
                reason="Criterion: should be, a int, float or string, a list (of int, float or str) or a dict.",
                dbg_info={"element": input_values},
            )
        return input_values

    # only allow overriding values (for now)

    def override(self, desc: dict[str, Any]) -> None:
        """
        Replace the value of the criterion using a descriptor containing the
        said value

        :param desc: descriptor supposedly containing a ``values`` entry
        """
        assert "values" in desc
        self._input_values = self.__sanitize_values(desc["values"])
        self._values = None
        self._expanded = False

    def intersect(self, other: Self) -> None:
        """
        Update the calling Criterion with the intersection of the current
        range of possible values with the one given as a parameters.

        This is used to refine overridden per-TE criterion according to
        system-wide's

        :param other: An other criterion object to build the intersection of.
        """
        assert isinstance(other, Criterion)
        assert self._name == other.name
        assert self._expanded
        assert other.expanded

        # None is special value meaning, discard this criterion because
        # irrelevant
        if self._values is None or other.values is None:
            self._values = None
        else:
            self._values = self._values.intersection(other.values)

    def is_empty(self) -> bool:
        """
        Is the current set of values empty
        May lead to errors, as it may indicates no common values has been
        found between user and system specifications

        :return: True if the value set is empty.
        """
        assert self._expanded
        return self._values is None or len(self._values) == 0

    def is_discarded(self) -> bool:
        """Should this criterion be ignored from the current TE generaiton ?"""
        return self._input_values is None

    def is_local(self) -> bool:
        """Is the criterion local ? (program-scoped)"""
        return self._local

    def is_env(self) -> bool:
        """Is this criterion targeting a component used as an env var ?"""
        return self._is_env

    @property
    def values(self) -> set[int | float | str]:
        """
        Get the ``value`` attribute of this criterion.

        :return: values of this criterion
        """
        assert self._expanded
        assert isinstance(self._values, set)
        return self._values

    def __len__(self) -> int:
        """
        Return the number of values this criterion holds.

        :return: the value list count
        """
        assert self._expanded
        assert self._values is not None
        return len(self._values)

    @property
    def name(self) -> str:
        """
        Get the ``name`` attribute of this criterion.

        :return: name of this criterion
        """
        return self._name

    @property
    def subtitle(self) -> str:
        """
        Get the ``subtitle`` attribute of this criterion.

        :return: subtitle of this criterion
        """
        return self._subtitle

    @property
    def numeric(self) -> bool:
        """
        Return if this criterion a numeric criterion (or a string iterator).

        :return: numeric of this criterion
        """
        return self._numeric

    def concretize_value(self, val: str = "") -> str:
        """
        Return the exact string mapping this criterion, according to the specification.
        (is it aliased ? should the option be put before/after the value?...)

        :param val: value to add with prefix
        :return: values with aliases replaced
        """
        # replace value with alias (if defined)
        val = str(self.aliased_value(val))
        # put value before of after the defined prefix
        elt = self._prefix + val if self._after else val + self._prefix
        # return the elt. up to the caller to determine
        # if this should be added as an arg or an env
        # ==> is_env()
        return elt

    def aliased_value(self, val: str) -> str:
        """
        Check if the given value has an alias for the current criterion.
        An alias is the value replacement to use instead of the one defined by
        test configuration. This allows to split test logic from runtime
        semantics.

        For instance, TEs manipulate 'ib' as a value to depict the 'infiniband'
        network layer. But once the test has to be built, the term will change
        depending on the runtime carrying it, the value may be different from
        a runtime to another

        :param val: string with aliases to be replaced
        :return: The aliased value.
        """
        return self._alias[val] if val in self._alias else val

    @staticmethod
    def __convert_sequence_to_list(
        node: dict[str, str | int | float], s: int = -1, e: int = -1
    ) -> list[int | float]:
        """
        Converts a sequence (as a string) to a valid list of values.

        :param node: dictionary to take the values from
        :param s: start (can be overridden by ``from`` in ``dic``), defaults to -1
        :param e: end (can be overridden by ``to`` in ``dic``), defaults to -1
        :return: list of values
        """

        values: list[int | float] = []

        # these must be integers
        def _convert_sequence_item_to_int(val: str | int | float) -> int | float:
            """
            Helper to convert a string-formatted number to a valid repr.

            :param val: the string-based number to convert
            :raises CommonException.BadTokenError: val is not a number
            :return: the number

            # noqa: DAR401
            # noqa: DAR402
            """
            if not isinstance(val, int) or not isinstance(val, float):
                try:
                    n = float(val)
                    if n.is_integer():
                        return int(n)
                    else:
                        return n
                except ValueError as ve:
                    raise ve
            else:
                return val

        start = _convert_sequence_item_to_int(node.get("from", s))
        end = _convert_sequence_item_to_int(node.get("to", e))
        of = _convert_sequence_item_to_int(node.get("of", 1))

        op = str(node.get("op", "seq")).lower()

        if op in ["seq", "arithmetic", "ari"]:
            assert isinstance(start, int) and isinstance(end, int) and isinstance(of, int)
            values = list(range(start, end + 1, of))
        elif op in ["mul", "geometric", "geo"]:
            if start == 0:
                values.append(0)
            elif of in [-1, 0, 1]:
                values.append(start**of)
            else:
                cur = start
                while cur <= end:
                    values.append(cur)
                    cur *= of
        elif op in ["pow", "powerof"]:
            if of == 0:
                values.append(0)
            start = math.ceil(start ** (1 / of))
            end = math.floor(end ** (1 / of))
            for i in range(start, end + 1):  # type: ignore
                values.append(i**of)
        else:
            io.console.warn("failure in Criterion sequence!")

        return values

    @property
    def expanded(self) -> bool:
        return self._expanded

    @property
    def min_value(self) -> int | float | str:
        assert self._expanded
        assert self._values is not None
        return min(self._values)

    @property
    def max_value(self) -> int | float | str:
        assert self._expanded
        assert self._values is not None
        return max(self._values)

    def expand_values(self, reference: Self | None = None) -> None:
        """Browse values for the current criterion and make it ready to generate combinations."""
        start = 0
        end = 100

        if self.expanded:
            return
        if self._input_values is None:
            self._values = None
            self._expanded = True
            return
        if reference is not None:
            assert isinstance(reference, Criterion)
            if not reference.expanded:
                reference.expand_values()

            if not reference.is_discarded():
                ref_min = reference.min_value
                ref_max = reference.max_value

                assert isinstance(ref_min, int)
                assert isinstance(ref_max, int)

                start = ref_min
                end = ref_max

        io.console.crit_debug(f"Expanding {self.name}: {self._input_values}")
        values: set[int | float | str] = set()
        if self._numeric is True:
            for v in self._input_values:
                if isinstance(v, (int, float)):
                    values.add(v)
                elif isinstance(v, dict):
                    for v in self.__convert_sequence_to_list(v, s=start, e=end):
                        assert isinstance(v, (int, float))
                        values.add(v)
                else:
                    raise TypeError(
                        "Only accept int, float or sequence (as string) as values for numeric iterators"
                    )
        else:
            for v in self._input_values:
                assert isinstance(v, (int, float, str))
                values.add(v)

        self._values = values
        self._expanded = True
        io.console.crit_debug(f"EXPANDED {self.name}: {self._values}")
        # TODO: handle criterion dependency (ex: n_mpi: ['n_node * 2'])

    def __repr__(self) -> str:
        return repr(self.__dict__)

    def __rich_repr__(self) -> Iterable[tuple[str, Any]]:
        return self.__dict__.items()


class Combination:
    """
    A combination maps the actual concretization from multiple criterion.

    Given a set of criterion, each having a list of values.
    A combination carrie, for each criterions one of it's value.
    This represent a set of value that bind a list of criterion to one specific test value.
    """

    def __init__(self, crit_desc: dict[str, Criterion], comb: dict, resources: list[int] | None):
        """
        Build a combination from two components:
        - the actual combination dict
        - the dict of criterions

        :param crit_desc: dict of criterions (=their full description)
            represented in the current combination.
        :param comb: actual combination dict (k=criterion name, v=actual value)
        :param resources: The resources used when running the job with this specific combination.
        """
        self._criterions = crit_desc
        self._combination = comb
        self._resources = resources

    def get(self, k: str, dflt: Any = None) -> Any:
        """
        Retrieve the actual value for a given combination element.

        :param k: value to retrieve
        :param dflt: default value if k is not a valid key
        :return: The combination value of the criterion with name k, or default value.
        """
        if k not in self._combination:
            return dflt
        return self._combination[k]

    def items(self) -> ItemsView:
        """
        Get the combination dict.

        :return: the whole combination dict.
        """
        return self._combination.items()

    def translate_to_str(self) -> str:
        """
        Translate the actual combination in a pretty-format string.

        This is mainly used to generate actual test names

        :return: A stringify version of the combination.
        """
        c = self._criterions
        string = []
        # each combination is built following: 'defined-prefix+value'
        for n in sorted(self._combination.keys()):
            subtitle = c[n].subtitle
            string.append(subtitle + str(self._combination[n]).replace(" ", "-"))
        return "_".join(string)

    def translate_to_command(self) -> tuple[list[str], list[str], list[str]]:
        """
        Translate the actual combination is tuple of three elements, based
        on the representation of each criterion in the test semantic. It builds
        tokens to provide to properly build the test command. It can
        either be:

        1. an environment variable to export before the test to run (gathering
           system-scope and program-scope elements)
        2. a runtime argument
        3. a program-level argument (through custom-made iterators)

        :return: (environment variables, wrapper argument, program argument)
        """
        args = []
        envs = []
        params = []
        # for each elt, where k is the criterion name, v is the actual value
        for k_elt, v_elt in self._combination.items():
            c = self._criterions[k_elt]
            # concretize_value() gathers both criterion label & value according
            # to specs (before, after, aliasing...)
            value = c.concretize_value(str(v_elt))

            if c.is_env():
                envs.append(value)
            elif c.is_local():
                params.append(value)
            else:
                args.append(value)
        return (envs, args, params)

    def get_combinations(self) -> dict[str, Any]:
        """
        Translate the combination into a dictionary.

        :return: configuration in the shape of a python dict
        """
        return self._combination

    @property
    def resources(self) -> list[int] | None:
        return self._resources

    def __repr__(self) -> str:
        return repr(self.__dict__)

    def __rich_repr__(self) -> Iterable[tuple[Any, Any]]:
        return self.__dict__.items()


class Series:
    """
    A series ties a test expression (:class:`TEDescriptor`) to the possible values
    which can be taken for each criterion to build test sets.
    A series can be seen as the Combination generator for a given :class:`TEDescriptor`
    """

    def __init__(self, dict_of_criterion: dict[str, Criterion]):
        """
        Build a series, by extracting the list of values.
        Note that here, the dict also contains program-based criterions.
        :param dict_of_criterion: values to build the series with
        """
        self._values: list[set[int | float | str]] = []
        self._keys: list[str] = []
        # this has to be saved, need to be forwarded to each combination
        self._dict: dict[str, Criterion] = dict_of_criterion  # type: ignore
        for name, node in dict_of_criterion.items():
            assert isinstance(node, Criterion)
            assert name == node.name
            self._values.append(node.values)
            self._keys.append(node.name)

    def generate(self) -> Iterable[Combination]:
        """Generator to build each combination"""
        for combination in itertools.product(*self._values):
            d = {self._keys[i]: val for i, val in enumerate(combination)}
            if not valid_combination(d):
                continue
            resources: list[int] | None = get_resources(d)
            yield Combination(self._dict, d, resources)

    def __repr__(self) -> str:
        return repr(self.__dict__)

    def __rich_repr__(self) -> Iterable[tuple[Any, Any]]:
        return self.__dict__.items()


def initialize_from_system() -> None:
    """Initialise system-wide criterions

    TODO: Move this function elsewhere."""
    # sanity checks
    if "criterion" not in GlobalConfig.root:
        GlobalConfig.root.set_internal("crit_obj", {})
    else:
        # raw YAML objects
        runtime_iterators = GlobalConfig.root["runtime"]["criterions"]
        criterion_iterators = GlobalConfig.root["criterion"]
        it_to_remove = []

        # if a criterion defined in criterion.yaml but
        # not declared as part of a runtime, the criterion
        # should be silently discarded
        # here is the purpose
        for it in criterion_iterators.keys():
            if it not in runtime_iterators:
                io.console.warn("Undeclared criterion " "as part of runtime: '{}' ".format(it))
            elif criterion_iterators[it]["values"] is None:
                io.console.debug(
                    "No combination found for {}," " removing from schedule".format(it)
                )
            else:
                continue

            io.console.info("Removing '{}'".format(it))
            it_to_remove.append(it)

        # register the new dict {criterion_name: Criterion object}
        # the criterion object gathers both information from runtime & criterion
        GlobalConfig.root.set_internal(
            "crit_obj",
            {
                k: Criterion(k, {**runtime_iterators[k], **criterion_iterators[k]})
                for k in criterion_iterators.keys()
                if k not in it_to_remove
            },
        )

    # convert any sequence into valid range of integers for

    # numeric criterions
    comb_cnt = 1
    for criterion in GlobalConfig.root.get_internal("crit_obj").values():
        criterion.expand_values()
        comb_cnt *= len(criterion)
    GlobalConfig.root.set_internal("comb_cnt", comb_cnt)


# pylint for python3.10 and pylint for python3.12 does not agree on if this should be snake case or upper case ...
first = True  # pylint: disable=invalid-name


def load_plugin() -> None:
    rt = GlobalConfig.root["runtime"]
    val = GlobalConfig.root["validation"]
    p_collection = GlobalConfig.root.get_internal("pColl")

    if "plugin" in rt:
        # Temporary, for compatibility with older buold base64 encoded profile. -- start
        plugin_code = rt["plugin"]
        if type(plugin_code) is not str:
            plugin_code = plugin_code.decode("utf-8")
        while plugin_code.count("\n") <= 1:
            io.console.warning(
                "Profile plugin still encoded in base64, please use pcvs profile edit -p to convert plugin."
            )
            import base64

            plugin_code = base64.b64decode(plugin_code).decode("utf-8")
        # end

        rt["pluginfile"] = os.path.join(val["buildcache"], "rt-plugin.py")
        with open(rt["pluginfile"], "w", encoding="utf-8") as fh:
            fh.write(plugin_code)
        try:
            p_collection.register_plugin_by_file(rt["pluginfile"], activate=True)
        except SyntaxError:
            io.console.critical(
                "Profile plugin encoded in base64, "
                "update plugin in profile file, "
                'base64 -d <<< "<plugin>", '
                "or by using `pcvs edit -p`"
            )
    elif "defaultplugin" in rt:
        p_collection.activate_plugin(rt["defaultplugin"])


def get_plugin() -> Collection:
    """Get the current validation plugin for the run."""
    global first
    rt = GlobalConfig.root["runtime"]
    plugin = GlobalConfig.root.get_internal("pColl")
    assert isinstance(plugin, Collection)

    if first and ("plugin" in rt or "defaultplugin" in rt):
        first = not first
        load_plugin()

    return plugin


def valid_combination(dic: dict[str, int | float | str]) -> bool:
    """
    Check if dict is a valid criterion combination.

    :param dic: dict to check
    :return: True if dic is a valid combination
    """
    ret: bool | None = get_plugin().invoke_plugins(
        Plugin.Step.TEST_EVAL, config=GlobalConfig.root, combination=dic
    )

    # by default, no plugin = always true
    if ret is None:
        ret = True

    return ret


def get_resources(dic: dict[str, int | float | str]) -> list[int] | None:
    """Get the resources needed for a job."""
    res = get_plugin().try_invoke_plugins(
        Plugin.Step.TEST_EVAL, method="get_resources", combination=dic
    )
    assert res is None or isinstance(res, list)
    return res
