import base64
import json
import os
import shlex
from enum import IntEnum

from pcvs.helpers import log
from pcvs.helpers.criterion import Combination
from pcvs.helpers.system import ValidationScheme


class Test:
    """Smallest component of a validation process.

    A test is basically a shell command to run. Depending on its post-execution
    status, a success or a failure can be determined. To handle such component
    in a convenient way, more information can be attached to the command like a
    name, the elapsed time, the output, etc.

    In order to make test content flexible, there is no fixed list of
    attributes. A Test() constructor is initialized via (*args, **kwargs), to
    populate a dict `_array`.

    :cvar int Timeout_RC: special constant given to jobs exceeding their time limit.
    :cvar str NOSTART_STR: constant, setting default output when job cannot be run.
    """
    Timeout_RC = 127
    res_scheme = ValidationScheme("test-result")

    NOSTART_STR = b"This test cannot be started."

    class State(IntEnum):
        """Provide Status management, specifically for tests/jobs.

        Defined as an enum, it represents different states a job can take during
        its lifetime. As tests are then serialized into a JSON file, there is
        no need for construction/representation (as done for Session states).

        :var int WAITING: Job is currently waiting to be scheduled
        :var int IN_PROGRESS: A running Set() handle the job, and is scheduled
            for run.
        :var int SUCCEED: Job successfully run and passes all checks (rc,
            matchers...)
        :var int FAILED: Job didn't suceed, at least one condition failed.
        :var int ERR_DEP: Special cases to manage jobs descheduled because at
            least one of its dependencies have failed to complete.
        :var int ERR_OTHER: Any other uncaught situation.
        """
        WAITING = 0
        IN_PROGRESS = 1
        SUCCESS = 2
        FAILURE = 3
        ERR_DEP = 4
        ERR_OTHER = 5

        def __str__(self):
            """Stringify to return the label.

            :return: the enum name
            :rtype: str
            """
            return self.name

        def __repr__(self):
            """Enum representation a tuple (name, value).

            :return: a tuple mapping the enum.
            :rtype: tuple
            """
            return "({}, {})".format(self.name, self.value)

    def __init__(self, **kwargs):
        """constructor method.

        :param kwargs: flexible list of arguments to initialize a Test with.
        :type kwargs: dict
        """
        self._rc = 0
        self._comb = kwargs.get('comb')
        self._cwd = kwargs.get('wd')
        self._exectime = 0.0
        self._output = None
        self._state = Test.State.WAITING
        self._dim = kwargs.get('dim', 1)
        self._testenv = kwargs.get('environment')
        self._id = {
            'te_name': kwargs.get('te_name', 'noname'),
            'label': kwargs.get('label', 'nolabel'),
            'subtree': kwargs.get('subtree', ''),
            'comb': self._comb.translate_to_dict() if self._comb else {}
        }
        comb_str = self._comb.translate_to_str() if self._comb else None

        self._id['fq_name'] = Test.compute_fq_name(
            self._id['label'],
            self._id['subtree'],
            self._id['te_name'],
            comb_str,
            suffix=kwargs.get('user_suffix'))

        self._execmd = kwargs.get('command', '')
        self._data = {
            'metrics': None,
            'tags': kwargs.get('tags', []),
            'artifacts': kwargs.get('artifacts', {}),

        }
        self._validation = {
            'matchers': kwargs.get('matchers'),
            'script': kwargs.get('valscript'),
            'expect_rc': kwargs.get('rc', 0),
            'time': kwargs.get('time', 0),
            'delta': kwargs.get('delta', 0),
        }

        self._mod_deps = kwargs.get("mod_deps", [])
        self._depnames = kwargs.get('job_deps', [])
        self._deps = []

    @property
    def tags(self):
        """Getter for the full list of tags.

        :return: the list of of tags
        :rtype: list
        """
        return self._data['tags']

    @property
    def label(self):
        """Getter to the test label.

        :return: the label
        :rtype: str
        """
        return self._id["label"]

    @property
    def name(self):
        """Getter for fully-qualified job name.

        :return: test name.
        :rtype: str
        """
        return self._id['fq_name']

    @property
    def subtree(self):
        """Getter to the test subtree.

        :return: test subtree.
        :rtype: str.
        """
        return self._id["subtree"]

    @property
    def te_name(self):
        """Getter to the test TE name.

        :return: test TE name.
        :rtype: str.
        """

        return self._id["te_name"]

    @property
    def combination(self):
        """Getter to the test combination dict.

        :return: test comb dict.
        :rtype: dict
        """

        return self._comb

    @property
    def command(self):
        """Getter for the full command.

        This is a real command, executed in a shell, coming from user's
        specificaition. It should not be confused with `wrapped_command`.

        :return: unescaped command line
        :rtype: str
        """
        return self._execmd

    @property
    def invocation_command(self):
        """Getter for the list_of_test.sh invocation leading to run the job.

        This command is under the form: `sh /path/list_of_tests.sh <test-name>`

        :return: wrapper command line
        :rtype: str
        """
        return self._invocation_cmd

    @property
    def job_deps(self):
        """"Getter to the dependency list for this job.

        The dependency struct is an array, where for each name (=key), the
        associated Job is stored (value)
        :return: the list of object-converted deps
        :rtype: list
        """
        return self._deps

    @property
    def job_depnames(self):
        """Getter to the list of deps, as an array of names.

        This array is emptied when all deps are converted to objects.

        :return: the array of dep names
        :rtype: list
        """
        return self._depnames

    @property
    def mod_deps(self):
        """Getter to the list of pack-manager rules defined for this job.

        There is no need for a ``_depnames`` version as these deps are provided
        as PManager objects directly.

        :return: the list of package-manager based deps.
        :rtype: list
        """
        return self._mod_deps

    def resolve_a_dep(self, name, obj):
        """Resolve the dep object for a given dep name.

        :param name: the dep name to resolve, should be a valid dep.
        :type name: str
        :param obj: the dep object, should be a Test()
        :type obj: :class:`Test`
        """
        if name not in self._depnames:
            return

        self._deps.append(obj)

    def has_completed_deps(self):
        """Check if the test can be scheduled.

        It ensures it hasn't been executed yet (or currently running) and all
        its deps are resolved and successfully run.

        :return: True if the job can be scheduled
        :rtype: bool
        """
        return not self.been_executed() and len([d for d in self._deps if not d.been_executed()]) == 0

    def has_failed_dep(self):
        """Check if at least one dep is blocking this job from ever be
        scheduled.

        :return: True if at least one dep is shown a `Test.State.FAILURE` state.
        :rtype: bool
        """
        return len([d for d in self._deps if d.state == Test.State.FAILURE]) > 0

    def first_incomplete_dep(self):
        """Retrive the first ready-for-schedule dep.

        This is mainly used to ease the scheduling process by following the job
        dependency graph.

        :return: a Test object if possible, None otherwise
        :rtype: :class:`Test` or NoneType
        """
        for d in self._deps:
            if d.has_completed_deps() and d.state == Test.State.WAITING:
                return d
        return None

    @property
    def timeout(self):
        """Getter for Test timeout in seconds.

        It cumulates timeout + tolerance, this value being passed to the
        subprocess.timeout.

        :return: an integer if a timeout is defined, None otherwise
        :rtype: int or NoneType
        """
        if self._validation['time'] == 0:
            return None
        return self._validation['time'] + self._validation['delta']

    def get_dim(self, unit="n_node"):
        """Return the orch-dimension value for this test.

        The dimension can be defined by the user and let the orchestrator knows
        what resource are, and how to 'count' them'. This accessor allow the
        orchestrator to exract the information, based on the key name.

        :param unit: the resource label, such label should exist within the test
        :type unit: str

        :return: The number of resource this Test is requesting.
        :rtype: int
        """
        return self._dim

    def save_final_result(self, rc=0, time=0.0, out=b'', state=None):
        """Build the final Test result node.

        :param rc: return code, defaults to 0
        :type rc: int, optional
        :param time: elapsed time, defaults to 0.0
        :type time: float, optional
        :param out: standard out/err, defaults to b''
        :type out: bytes, optional
        :param state: Job final status (if override needed), defaults to FAILED
        :type state: :class:`Test.State`, optional
        """
        if state is None:
            state = Test.State.SUCCESS if self._validation['expect_rc'] == rc else Test.State.FAILURE
        self.executed(state)
        self._rc = rc
        self._output = base64.b64encode(out).decode('ascii')
        self._exectime = time

        for elt_k, elt_v in self._data['artifacts'].items():
            if os.path.isfile(elt_v):
                with open(elt_v, 'rb') as fh:
                    self._data['artifacts'][elt_k] = base64.b64encode(
                        fh.read()).decode("ascii")

    def display(self):
        """Print the Test into stdout (through the manager)."""
        colorname = "yellow"
        icon = ""
        label = str(self._state)
        if self._state == Test.State.SUCCESS:
            colorname = "green"
            icon = "succ"
        elif self._state == Test.State.FAILURE:
            colorname = "red"
            icon = "fail"
        elif self._state == Test.State.ERR_DEP:
            colorname = "yellow"
            icon = "fail"

        log.manager.print_job(label, self._exectime, self.name,
                              colorname=colorname, icon=icon)
        if self._output:
            if (log.manager.has_verb_level("info") and self.state == Test.State.FAILURE) or log.manager.has_verb_level("debug"):
                log.manager.print(base64.b64decode(self._output))

    def executed(self, state=None):
        """Set current Test as executed.

        :param state: give a special state to the test, defaults to FAILED
        :param state: :class:`Test.State`, optional
        """
        self._state = state if type(
            state) == Test.State else Test.State.FAILURE

    def been_executed(self):
        """Cehck if job has been executed (not waiting or in progress).

        :return: False if job is waiting for scheduling or in progress.
        :rtype: bool
        """
        return self._state not in [Test.State.WAITING, Test.State.IN_PROGRESS]

    def pick(self):
        """Flag the job as picked up for scheduling."""
        self._state = Test.State.IN_PROGRESS

    @property
    def state(self):
        """Getter for current job state.

        :return: the job current status.
        :rtype: :class:`Test.State`
        """
        return self._state

    def to_json(self, strstate=False):
        """Serialize the whole Test as a JSON object.

        :return: a JSON object mapping the test
        :rtype: str
        """
        return {
            "id": self._id,
            "exec": self._execmd,
            "result": {
                "rc": self._rc,
                "state": str(self._state) if strstate else self._state,
                "time": self._exectime,
                "output": self._output,
            },
            "data": self._data,
        }

    def from_json(self, test_json: str) -> None:
        """Replace the whole Test structure based on input JSON.

        :param json: the json used to set this Test
        :type json: test-result-valid JSON-formated str
        """

        if isinstance(test_json, str):
            test_json = json.load(test_json)

        assert(isinstance(test_json, dict))
        self.res_scheme.validate(test_json)

        self._id = test_json.get("id")
        self._comb = Combination({}, self._id.get('comb'))
        self._execmd = test_json.get("exec")
        self._data = test_json.get("data")

        res = test_json.get("result")
        self._rc = res.get("rc")
        self._output = res.get("output")
        self._state = Test.State(res.get("state", Test.State.ERR_OTHER))
        self._exectime = res.get("time")

    def generate_script(self, srcfile):
        """Serialize test logic to its Shell representation.

        This script provides the shell sequence to put in a shell script
        switch-case, in order to reach that test from script arguments.

        :param srcfile: script filepath, to store the actual wrapped command.
        :type srcfile: str
        :return: the shell-compliant instruction set to build the test
        :rtype: str
        """
        pm_code = ""
        cd_code = ""
        env_code = ""
        cmd_code = ""
        post_code = ""

        self._invocation_cmd = 'sh {} {}'.format(srcfile, self._id['fq_name'])

        # if changing directory is required by the test
        if self._cwd is not None:
            cd_code += "cd '{}'\n".format(shlex.quote(self._cwd))

        # manage package-manager deps
        for elt in self._mod_deps:
            pm_code += "\n".join([elt.get(load=True, install=True)])

        # manage environment variables defined in TE
        if self._testenv is not None:
            for e in self._testenv:
                env_code += "{}; export {}\n".format(
                    shlex.quote(e), shlex.quote(e.split('=')[0]))

        # if test should be validated through a matching regex
        if self._validation['matchers'] is not None:
            for k, v in self._validation['matchers'].items():
                expr = v['expr']
                required = (v.get('expect', True) is True)
                # if match is required set 'ret' to 1 when grep fails
                post_code += "{echo} | {grep} '{expr}' {fail} ret=1\n".format(
                    echo='echo "$output"',
                    grep='grep -qP',
                    expr=shlex.quote(expr),
                    fail='||' if required else "&&")

        # if a custom script is provided (in addition or not to matchers)
        if self._validation['script'] is not None:
            post_code += "{echo} | {script}; ret=$?".format(
                echo='echo "$output"',
                script=shlex.quote(self._validation['script'])
            )

        cmd_code = self._execmd

        return """
        "{name}")
            if test -n "$PCVS_SHOW"; then
                test "$PCVS_SHOW" = "env" -o "$PCVS_SHOW" = "all" &&  echo '{p_env}'
                test "$PCVS_SHOW" = "loads" -o "$PCVS_SHOW" = "all" &&  echo '{p_pm}'
                test "$PCVS_SHOW" = "cmd" -o "$PCVS_SHOW" = "all" &&  echo {p_cmd}
                exit 0
            fi
            {cd_code}
            {pm_code}
            {env_code}
            output=$({cmd_code} 2>&1)
            ret=$?
            test -n "$output" && echo "$output"
            {post_code}
            ;;""".format(
            p_cmd="{}".format(shlex.quote(cmd_code)),
            p_env="{}".format(env_code),
            p_pm="{}".format(pm_code),
            cd_code=cd_code,
            pm_code=pm_code,
            env_code=env_code,
            cmd_code=cmd_code,
            post_code=post_code,
            name=self._id['fq_name']
        )

    @classmethod
    def compute_fq_name(self, label, subtree, name, combination=None, suffix=None):
        """Generate the fully-qualified (dq) name for a test, based on :
            - the label & subtree (original FS tree)
            - the name (the TE name it is originated)
            - a potential extra suffix
            - the combination PCVS computed for this iteration."""
        return "_".join(filter(None, [
            "/".join(filter(None, [
                label,
                subtree,
                name])),
            suffix,
            combination]))
