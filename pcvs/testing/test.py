import base64
import os
import shlex
from enum import IntEnum

from pcvs import PATH_INSTDIR
from pcvs.helpers import log
from pcvs.helpers.pm import PManager
from pcvs.helpers import communications

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
        SUCCEED = 2
        FAILED = 3
        ERR_DEP = 4
        ERR_OTHER = 5

        def __str__(self):
            """Stringify to return the label.

            :return: the enum name
            :rtype: str
            """
            return self.name

        def __repr__(self):
            """Enum represenation a tuple (name, value).

            :return: a tuple mapping the enum.
            :rtype: tuple
            """
            return (self.name, self.value)

    def __init__(self, **kwargs):
        """constructor method.

        :param kwargs: flexible list of arguments to initialize a Test with.
        :type kwargs: dict
        """
        self._array = kwargs
        self._rc = 0
        self._time = 0.0
        self._out = None
        self._state = Test.State.WAITING

        if 'dep' in self._array:
            deparray = self._array['dep']
            self._array['dep'] = {k: None for k in deparray}

    @property
    def name(self):
        """Getter for fully-qualified job name.

        :return: test name.
        :rtype: str
        """
        return self._array['name']

    @property
    def command(self):
        """Getter for the full command.

        This is a real command, executed in a shell, coming from user's
        specificaition. It should not be confused with `wrapped_command`.

        :return: unescaped command line
        :rtype: str
        """
        return self._array['command']

    @property
    def wrapped_command(self):
        """Getter for the list_of_test.sh invocation leading to run the job.

        This command is under the form: `sh /path/list_of_tests.sh <test-name>`

        :return: wrapper command line
        :rtype: str
        """
        return self._array['wrapped_command']

    @property
    def deps(self):
        """"Getter to the dependency list for this job.

        The dependency struct is an array, where for each name (=key), the
        associated Job is stored (value)
        :return: the dict, potentially not resolved yet
        :rtype: dict
        """
        return self._array["dep"]

    def set_dep(self, name, obj):
        """Resolve the dep object for a given dep name.

        :param name: the dep name to resolve, should be a valid dep.
        :type name: str
        :param obj: the dep object, should be a Test()
        :type obj: :class:`Test`
        """
        assert(name in self._array['dep'])
        self._array['dep'][name] = obj

    def is_pickable(self):
        """Check if the test can be scheduled.

        It ensures it hasn't been executed yet (or currently running) and all
        its deps are resolved and successfully run.

        :return: True if the job can be scheduled
        :rtype: bool
        """
        return not self.been_executed() and len([d for d in self.deps.values() if not d.been_executed()]) == 0

    def has_failed_dep(self):
        """Check if at least one dep is blocking this job from ever be
        scheduled.

        :return: True if at least one dep is shown a `Test.State.FAILED` state.
        :rtype: bool
        """
        return len([d for d in self.deps.values() if d.state == Test.State.FAILED]) > 0

    def first_valid_dep(self):
        """Retrive the first ready-for-schedule dep.

        This is mainly used to ease the scheduling process by following the job
        dependency graph.

        :return: a Test object if possible, None otherwise
        :rtype: :class:`Test` or NoneType
        """
        for d in self.deps.values():
            if d.is_pickable():
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
        if self._array['time'] is None:
            return None
        return self._array['time'] + self._array['delta']

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
        return self._array['nb_res']

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
            state = Test.State.SUCCEED if self._rc == rc else Test.State.FAILED
        self.executed(state)
        self._rc = rc
        self._out = base64.b64encode(out).decode('ascii')
        self._time = time

        for elt_k, elt_v in self._array['artifacts'].items():
            if os.path.isfile(elt_v):
                with open(elt_v, 'rb') as fh:
                    self._array['artifacts'][elt_k] = base64.b64encode(
                        fh.read()).decode("ascii")

    def display(self):
        """Print the Test into stdout (through the manager)."""
        colorname = "yellow"
        icon = ""
        label = str(self._state)
        if self._state == Test.State.SUCCEED:
            colorname = "green"
            icon = "succ"
        elif self._state == Test.State.FAILED:
            colorname = "red"
            icon = "fail"
        elif self._state == Test.State.ERR_DEP:
            colorname = "yellow"
            icon = "fail"

        communications.CommManager.send(label, self.to_json())
        log.manager.print_job(label, self._time, self.name,
                              colorname=colorname, icon=icon)
        if self._out:
            if (log.manager.has_verb_level("info") and self.state == Test.State.FAILED) or log.manager.has_verb_level("debug"):
                log.manager.print(base64.b64decode(self._out))

    def executed(self, state=None):
        """Set current Test as executed.

        :param state: give a special state to the test, defaults to FAILED
        :param state: :class:`Test.State`, optional
        """
        self._state = state if type(state) == Test.State else Test.State.FAILED

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

    def to_json(self):
        """Serialize the whole Test as a JSON object.

        :return: a JSON object mapping the test
        :rtype: str
        """
        return {
            "id": {
                "te_name": self._array["te_name"],
                "label": self._array["label"],
                "subtree": self._array["subtree"],
                "full_name": self._array["name"]
            },
            "exec": self._array["command"],
            "result": {
                "rc": self._rc,
                "state": self._state,
                "time": self._time,
                "output": self._out,
            },
            "data": {
                "tags": self._array['tags'],
                "metrics": "TBD",
                "artifacts": self._array['artifacts'],
                "combination": self._array['comb_dict']
            }
        }

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

        self._array['wrapped_command'] = 'sh {} {}'.format(
            srcfile, self._array['name'])

        # if changing directory is required by the test
        if self._array['chdir'] is not None:
            cd_code += "cd '{}'\n".format(shlex.quote(self._array['chdir']))

        # manage package-manager deps
        if self._array['dep'] is not None:
            pm_code += "\n".join([
                elt.get(load=True, install=True)
                for elt in self._array['dep']
                if isinstance(elt, PManager)
            ])

        # manage environment variables defined in TE
        if self._array['env'] is not None:
            for e in self._array['env']:
                env_code += "{}; export {}\n".format(
                    shlex.quote(e), shlex.quote(e.split('=')[0]))

        # if test should be validated through a matching regex
        if self._array['matchers'] is not None:
            for k, v in self._array['matchers'].items():
                expr = v['expr']
                required = (v.get('expect', True) is True)
                # if match is required set 'ret' to 1 when grep fails
                post_code += "{echo} | {grep} '{expr}' {fail} ret=1\n".format(
                    echo='echo "$output"',
                    grep='grep -qP',
                    expr=shlex.quote(expr),
                    fail='||' if required else "&&")

        # if a custom script is provided (in addition or not to matchers)
        if self._array['valscript'] is not None:
            post_code += "{echo} | {script}; ret=$?".format(
                echo='echo "$output"',
                script=shlex.quote(self._array['valscript'])
            )

        cmd_code = self._array['command']

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
            name=self._array['name']
        )
