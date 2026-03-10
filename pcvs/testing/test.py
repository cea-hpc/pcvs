import base64
import hashlib
import json
import os
import re
import shlex
import subprocess
from typing import Any
from typing import Iterable

from typing_extensions import Self

from pcvs import io
from pcvs.backend.metaconfig import GlobalConfig
from pcvs.helpers.criterion import Combination
from pcvs.helpers.pm import PManager
from pcvs.helpers.validation import ValidationScheme
from pcvs.plugins import Plugin
from pcvs.testing.teststate import TestState


class Test:
    r"""
    Smallest component of a validation process.

    A test is basically a shell command to run. Depending on its post-execution
    status, a success or a failure can be determined. To handle such component
    in a convenient way, more information can be attached to the command like a
    name, the elapsed time, the output, etc.

    :cvar NOSTART_STR: constant, setting default output when job cannot be run.
    :vartype NOSTART_STR: :py:obj:`str`
    :cvar DISCARDED_STR: constant, setting default output for discarded test.
    :vartype DISCARDED_STR: :py:obj:`str`
    """

    res_scheme = ValidationScheme("test-result")

    NOSTART_STR = "This test cannot be started."
    DISCARDED_STR = "This test has failed to be scheduled. Discarded."

    def __init__(
        self,
        comb: Combination | None = None,
        wd: str | None = None,
        resources: list[int] | None = None,
        environment: list[str] | None = None,
        te_name: str = "noname",
        label: str = "nolabel",
        subtree: str = "nosubtree",
        user_suffix: str | None = None,
        command: str = "",
        metrics: dict[str, dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        artifacts: dict | None = None,
        validation: dict | None = None,
        mod_deps: list[PManager] | None = None,
        job_deps: list[str] | None = None,
    ):
        """
        Construct a Test.

        :param comb: Criterion expanded combination for this specific test.
        :param wd: Test working directory.
        :param resources: Resources consumed by the test (cpu_cores / nodes),
            scheduler heuristic to avoid running to much jobs in scheduler that badly scale (like slurm).
        :param environment: Environment variables used when running the test.
        :param te_name: Test name.
        :param label: Test label.
        :param subtree: Sub directory of the test from the pcvs execution directory.
        :param user_suffix: Test suffix.
        :param command: The command used to run the test.
        :param metrics: Dictionary of regexs to get data from test output, stored in test results.
        :param tags: Tets tags, used to filter test execution and console output of test stdout/stderr.
        :param artifacts: Artifacts (files) that will be saved in test data after test run,
            a dict mapping artifact name in test data to files names to read from the disks.
        :param validation: Validation configuration. Contain some to all of the following:

          - expected exit code
          - soft_timeout
          - hard_timeout
          - dynamic time validation ``((mean + tolerance) * weight)``
          - regex matcher
          - validation script path
        :param mod_deps: Package manager dependency (modules or spack).
        :param job_deps: Other jobs name that this test depends on (like compilation phases).
        """
        # None args initializer
        metrics = {} if metrics is None else metrics
        tags = [] if tags is None else tags
        artifacts = {} if artifacts is None else artifacts
        validation = {} if validation is None else validation
        mod_deps = [] if mod_deps is None else mod_deps
        job_deps = [] if job_deps is None else job_deps

        # Basic Info Compute
        comb_str: str | None = comb.translate_to_str() if comb is not None else None
        fq_name: str = Test.compute_fq_name(label, subtree, te_name, user_suffix, comb_str)
        jid: str = self.get_jid_from_name(fq_name)
        cores_per_nodes: int = GlobalConfig.root.get("machine", {}).get("cores_per_nodes", 1)
        _resources: list[int] = resources if resources is not None else [1, cores_per_nodes]
        for r in _resources:
            assert r is not None

        # Identification infos
        self._jid: str = jid
        self._fq_name: str = fq_name
        self._te_name: str = te_name
        self._label: str = label
        self._subtree: str = subtree
        self._suffix: str = user_suffix if user_suffix is not None else ""

        # Advanced infos
        self._testenv: list[str] | None = environment
        self._execmd: str = command
        self._tags: list[str] = tags
        self._artifacts: dict = artifacts
        self._comb: Combination | None = comb
        self._comb_str: str | None = comb_str
        self._resources: list[int] = _resources
        self._metrics: dict[str, dict[str, Any]] = metrics
        self._mod_deps: list[PManager] = mod_deps
        self._depnames: list[str] = job_deps

        # Runtime infos (change during the run, the others vars should be const)
        self._rc: int = 0
        self._cwd: str | None = wd
        self._exectime: float = 0.0
        self._output: str = ""
        self._state: TestState = TestState.WAITING
        self._deps: list[Self] = []
        self._dependee: list[Self] = []
        self._has_hard_timeout: bool = False
        self._invocation_cmd: str | None = (
            None  # Command that launch list_of_test.sh (not the test command itself)
        )

        # Validation Infos / Compute
        self._expect_rc = validation.get("expect_exit", 0)
        self._time_validation: dict | None = None
        if "time" in validation:
            self._time_validation = {
                "mean": validation["time"].get("mean", -1),
                "tolerance": validation["time"].get("tolerance", 0),
                "coef": validation["time"].get("coef", 1.5),
            }
        self._soft_timeout: int | None = validation.get("time", {}).get("soft_timeout", None)
        self._hard_timeout: int | None = validation.get("time", {}).get("hard_timeout", None)
        self._matchers: dict | None = validation.get("match", None)
        self._analysis: dict | None = validation.get("analysis", None)
        self._script: str = validation.get("script", {}).get("path", None)

        self._output_info: dict[str, Any] = {"file": None, "offset": -1, "length": 0}
        # alloc tracking number, used by job manager to track job allocation
        self.alloc_tracking = 0

    @property
    def jid(self) -> str:
        """
        Getter for unique Job ID within a run.

        This attribute is generally set by the manager once job is uploaded
        to the dataset.

        :return: a unique hash of the job name
        """
        return self._jid

    @property
    def basename(self) -> str:
        """Get fully-qualified name."""
        return Test.compute_fq_name(self._label, self._subtree, self._te_name)

    @property
    def tags(self) -> list[str]:
        """
        Getter for the full list of tags.

        :return: the list of of tags
        """
        return self._tags

    @property
    def label(self) -> str:
        """
        Getter to the test label.

        :return: the label
        """
        return self._label

    @property
    def name(self) -> str:
        """
        Getter for fully-qualified job name.

        :return: test name.
        """
        return self._fq_name

    @property
    def subtree(self) -> str:
        """
        Getter to the test subtree.

        :return: test subtree.
        """
        return self._subtree

    @property
    def te_name(self) -> str:
        """
        Getter to the test TE name.

        :return: test TE name.
        """

        return self._te_name

    @property
    def combination(self) -> Combination:
        """
        Getter to the test combination dict.

        :return: test comb dict.
        """
        assert self._comb is not None
        return self._comb

    @property
    def command(self) -> str:
        """
        Getter for the full command.

        This is a real command, executed in a shell, coming from user's
        specificaition. It should not be confused with `invocation_command`.

        :return: unescaped command line
        """
        return self._execmd

    @property
    def invocation_command(self) -> str:
        """
        Getter for the list_of_test.sh invocation leading to run the job.

        This command is under the form: `sh /path/list_of_tests.sh <test-name>`

        :return: wrapper command line
        """
        assert self._invocation_cmd is not None
        return self._invocation_cmd

    @property
    def job_deps(self) -> list[Self]:
        """
        Getter to the dependency list for this job.

        The dependency struct is an array, where for each name (=key), the
        associated Job is stored (value)

        :return: the list of object-converted deps
        """
        return self._deps

    @property
    def job_depnames(self) -> list[str]:
        """
        Getter to the list of deps, as an array of names.

        This array is emptied when all deps are converted to objects.

        :return: the array of dependency names
        """
        return self._depnames

    @property
    def mod_deps(self) -> list[PManager]:
        """
        Getter to the list of pack-manager rules defined for this job.

        There is no need for a ``_depnames`` version as these deps are provided
        as PManager objects directly.

        :return: the list of package-manager based deps.
        """
        return self._mod_deps

    @classmethod
    def get_jid_from_name(cls, name: str) -> str:
        """
        Compute a Test ID from a Test name.

        :param name: The name of the Test.
        :return: The test id.
        """
        namebytes = name.encode("utf-8")
        return hashlib.md5(namebytes).hexdigest()

    def get_dep_graph(self) -> dict[str, dict]:
        """
        Get the dependency graph from that test.

        Associate every dependency name to their own recursive dependency graph.

        :return: The dependency Graph build from dicts.
        """
        res = {}
        for d in self._deps:
            res[d.name] = d.get_dep_graph()
        return res

    def resolve_a_dep(self, name: str, obj: Self) -> None:
        """Resolve the dep object for a given dep name.

        :param name: the dep name to resolve, should be a valid dep.
        :param obj: the dep object, should be a Test()
        """
        if name not in self._depnames:
            return

        if obj not in self._deps:
            self._deps.append(obj)

    def add_dependee(self, test: Self) -> None:
        """
        Add a Test to the list of test that depends on this test.

        :param test: the test to add.
        """
        self._dependee.append(test)

    def remove_dependee(self, test: Self) -> None:
        """
        Remove a Tets to the list of test that depends on this test.

        :param test: the test to remove.
        """
        self._dependee.remove(test)

    def transpose_deps(self) -> None:
        """Transpose the dependency graph to compute the dependee graph."""
        for test in self._deps:
            test.add_dependee(self)  # type: ignore

    def remove_test_from_deps(self) -> None:
        """
        Remove this Test from it's dependency dependee list.
        i.e. remove self from the dependee list of test that we depends on.
        """
        for test in self._deps:
            test.remove_dependee(self)  # type: ignore

    def should_run(self) -> bool:
        """Should the test be run."""
        # There is tests tat depends on this one, so it should be run.
        if len(self._dependee) > 0:
            return True
        valcfg = GlobalConfig.root["validation"]

        # Is this job included or excluded by job filter ?
        contain_allow_filter: bool = False
        for t, allow in valcfg["run_filter"].items():
            if allow:
                contain_allow_filter = True
                if t in self._tags:
                    return True
            else:
                if t in self._tags:
                    return False

        # if there is at least one allow filters, deny every thing that is not in it.
        if contain_allow_filter:
            return False
        # By default test is not filter.
        return True

    def has_completed_deps(self) -> bool:
        """
        Check if the test can be scheduled.

        Ensures all its deps are resolved and successfully run.

        :return: True if the job can be scheduled
        """
        return len([d for d in self._deps if not d.been_executed()]) == 0

    def has_failed_dep(self) -> bool:
        """
        Check if at least one dep is blocking this job from ever be scheduled.

        :return: True if at least one dep is shown a Failure state.
        """
        for d in self._deps:
            if d.state in TestState.bad_states():
                return True
        return False

    @property
    def soft_timeout(self) -> int:
        """
        Getter for Test timeout in seconds.

        timeout is (in order):
          1. explicitly defined
          2. OR extrapolated from defined result.mean
          3. set by default (GlobalConfig.root.validation.job_timeout)

        :return: an integer if a timeout is defined, None otherwise
        """

        if self._soft_timeout:
            return self._soft_timeout
        if self._time_validation and self._time_validation["mean"] > 0:
            mean = self._time_validation["mean"]
            tolerance = self._time_validation["tolerance"]
            coef = self._time_validation["coef"]
            assert isinstance(mean, (int, float))
            assert isinstance(tolerance, (int, float))
            assert isinstance(coef, (int, float))
            return int((mean + tolerance) * coef)
        global_soft = GlobalConfig.root["validation"]["soft_timeout"]
        assert isinstance(global_soft, int)
        return global_soft

    @property
    def hard_timeout(self) -> int:
        """
        Getter for Test hard timeout in seconds.

        :return: the hard timeout after which the job is killed.
        """
        if self._hard_timeout:
            return self._hard_timeout
        global_hard = GlobalConfig.root["validation"]["hard_timeout"]
        assert isinstance(global_hard, int)
        return global_hard

    def get_nb_nodes(self) -> int:
        """
        Return the first higher orcherstrator dimension value for this test (mostlikely the number of nodes).

        The dimension can be defined by the user and let the orchestrator knows
        what resource are, and how to 'count' them'. This accessor allow the
        orchestrator to extract the information, based on the key name.

        :return: The number of resource this Test is requesting.
        """
        if self._resources and len(self._resources) > 0:
            return self._resources[0]
        return 1

    @property
    def needed_resources(self) -> list[int]:
        """
        Return the orcherstrator resources used by the jobs

        The meaning for resources list is user defined and can vary depending on
        how test/plugin defines the resources and how the job orcherstrator
        of the wrapper defines themes.

        It will most likely be [nb_nodes, nb_cpu_per_nodes].
        But it could be [nb_nodes_lvl1, nb_nodes_lvl2, nb_nodes_lvl3, NUMA_NODE,
        UNIX_process, MPI_PROCESS, L3_CACHE, pthreads, L2_CACHE, omp_threads, L1_CACHE, ...].

        :return: The resources allocation list for the jobs.
        """
        return self._resources

    def save_final_result(
        self, rc: int = 0, time: float = 0.0, out: str = "", state: TestState | None = None
    ) -> None:
        """
        Build the final Test result node.

        :param rc: return code, defaults to 0
        :param time: elapsed time, defaults to 0.0
        :param out: standard out/err, default to ""
        :param state: Job final status (if override needed), defaults to None
        """
        _state: TestState
        if state is None:
            _state = TestState.SUCCESS if self._expect_rc == rc else TestState.FAILURE
        else:
            _state = state

        self.save_raw_run(rc=rc, out=out, time=time)
        self.save_status(_state)
        self.save_artifacts()

    def save_artifacts(self) -> None:
        """Read artifacts from disk for storage in test data."""
        for elt_k, elt_v in self._artifacts.items():
            if os.path.isfile(elt_v):
                with open(elt_v, "rb") as fh:
                    self._artifacts[elt_k] = fh.read()

    def save_raw_run(
        self,
        out: str | None = None,
        rc: int | None = None,
        time: float | None = None,
        hard_timeout: bool = False,
    ) -> None:
        """
        Save basic run information.

        :param out: standard out/err
        :param rc: return code
        :param time: elapsed time
        :param hard_timeout: has the test reach hard timeout and got killed.
        """
        if out is not None:
            self._output = out
        if rc is not None:
            self._rc = rc
        if time is not None:
            self._exectime = time
        self._has_hard_timeout = hard_timeout

    def extract_metrics(self) -> None:
        """Use user defined 'metrics' to grep requested information from test output and store themes."""
        for name in self._metrics.keys():
            node = self._metrics[name]

            try:
                ens = set if node["attributes"]["unique"] else list
            except KeyError:
                ens = list

            self._metrics[name]["values"] = list(ens(re.findall(node["key"], self._output)))

    def evaluate(self) -> None:
        """Evaluate test results to update the test state according to validation configuration."""
        if self._has_hard_timeout:
            self._state = TestState.HARD_TIMEOUT
            return

        state = TestState.SUCCESS

        # validation by return code
        if self._expect_rc != self._rc:
            state = TestState.FAILURE

        # validation through a matching regex
        if state == TestState.SUCCESS and self._matchers is not None:
            for _, v in self._matchers.items():
                expected = v.get("expect", True) is True
                found = re.search(v["expr"], self._output)
                io.console.debug(
                    f"Looking for expr: {v['expr']}, foud: {found}, expected: {expected}"
                )
                if (found and not expected) or (not found and expected):
                    state = TestState.FAILURE
                    break

        # validation throw a plugin
        if state == TestState.SUCCESS and self._analysis is not None:
            res = GlobalConfig.root.get_internal("pColl").invoke_plugins(
                Plugin.Step.TEST_RESULT_EVAL, analysis=self._analysis, job=self
            )
            if res is not None:
                state, self._soft_timeout = res

        # validation throw a custom script
        if state == TestState.SUCCESS and self._script is not None:
            try:
                s = subprocess.Popen(self._script, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                s.communicate()
                rc = s.returncode
            except Exception:
                rc = 42

            if self._expect_rc != rc:
                state = TestState.FAILURE

        # if the test succeed, check for soft timeout
        if (
            state == TestState.SUCCESS
            and self._soft_timeout is not None
            and self.time > self._soft_timeout
        ):
            state = TestState.SOFT_TIMEOUT

        self._state = state

    def save_status(self, state: TestState) -> None:
        """
        Set current Test state.

        :param state: give a special state to the test
        """
        assert isinstance(state, TestState)
        self._state = state

    def should_print(self) -> bool:
        """Should the test result be printed."""
        # No output recorded
        if not self._output:
            return False
        valcfg = GlobalConfig.root["validation"]

        # Is the test filtered
        contain_allow_filter: bool = False
        for t, allow in valcfg["print_filter"].items():
            if allow:
                contain_allow_filter = True
                if t in self._tags:
                    return True
            else:
                if t in self._tags:
                    return False

        # if there is allow filters, deny every thing that is not in it.
        if contain_allow_filter:
            return False

        # print policy
        if valcfg["print_policy"] == "all":
            return True
        if valcfg["print_policy"] == "none":
            return False
        if valcfg["print_policy"] == "errors" and self.state in TestState.bad_states():
            return True
        # don't print by default
        return False

    def get_state_fancy(self) -> tuple[str, str, str]:
        """Get the label, color & icon representing the status of the test."""
        label = str(self._state)
        color = "yellow"
        icon = ""

        if self._state == TestState.SUCCESS:
            color = "green"
            icon = "succ"
        elif self._state in [TestState.FAILURE, TestState.HARD_TIMEOUT]:
            color = "red"
            icon = "fail"
        elif self._state in [TestState.ERR_DEP, TestState.ERR_OTHER, TestState.SOFT_TIMEOUT]:
            color = "yellow"
            icon = "fail"
        return (label, color, io.console.utf(icon))

    def get_testinfo_fancy(self) -> str:
        """Get the test status string printed when running pcvs run."""
        label, color, icon = self.get_state_fancy()

        if self._state == TestState.HARD_TIMEOUT:
            timeout = self.hard_timeout
        elif self._state == TestState.SOFT_TIMEOUT:
            timeout = self.soft_timeout
        else:
            timeout = 0
        assert isinstance(timeout, int)
        timeout_str = f" ({timeout:5.2f}s)" if timeout > 0 else ""

        sep = io.console.utf("sep_v")
        return f"[{color} bold]   {icon} {self._exectime:8.2f}s{sep}{label:7}{timeout_str}{sep}{self.name}"

    def display(self) -> None:
        """Print the Test to console."""
        output = None
        if self.should_print():
            output = self._output

        io.console.print_job(
            self.get_testinfo_fancy(),
            self._state,
            self.label,
            "/{}".format(self.subtree) if self.subtree else "",
            output,
        )

    def been_executed(self) -> bool:
        """
        Check if job has been executed and result computed (not waiting, in progress or EXECUTED).

        :return: False if job is waiting for scheduling, in progress or waiting for post processing.
        """
        return self._state not in [TestState.WAITING, TestState.IN_PROGRESS, TestState.EXECUTED]

    def pick(self) -> None:
        """Flag the job as picked up for scheduling."""
        self._state = TestState.IN_PROGRESS

    @property
    def state(self) -> TestState:
        """
        Getter for current job state.

        :return: the job current status.
        """
        return self._state

    @property
    def output(self) -> str:
        """Getter for the test output."""
        return self._output

    @output.setter
    def output(self, output: str) -> None:
        """Setter for the test output."""
        self._output = output

    @property
    def b64_output(self) -> str:
        """Getter for the test output in base64."""
        return base64.b64encode(self._output.encode("utf-8")).decode("utf-8")

    @b64_output.setter
    def b64_output(self, v: str) -> None:
        """Setter for the test output in base64."""
        self._output = base64.b64decode(v.encode("utf-8")).decode("utf-8")

    @property
    def b64_output_bytes(self) -> bytes:
        """Getter for the test output in base64 as utf-8 encoded bytes."""
        return base64.b64encode(self._output.encode("utf-8"))

    @b64_output_bytes.setter
    def b64_output_bytes(self, output: bytes) -> None:
        """Setter for the test output in base64 as utf-8 decoded bytes."""
        self._output = base64.b64decode(output).decode("utf-8")

    @property
    def output_info(self) -> dict:
        """Info about the output (file, offset & length)."""
        return self._output_info

    @property
    def time(self) -> float:
        """Test execution time."""
        return self._exectime

    @property
    def retcode(self) -> int:
        """Return code of the test process."""
        return self._rc

    def to_json(self, strstate: bool = False) -> dict[str, Any]:
        """
        Serialize the whole Test as a JSON object.

        :param strstate: if test state should be serialised to string
        :return: a JSON dict mapping the test
        """
        output = self.output_info
        output["raw"] = self.b64_output
        res = {
            "id": {
                "jid": self._jid,
                "fq_name": self._fq_name,
                "te_name": self._te_name,
                "label": self._label,
                "subtree": self._subtree,
                "suffix": self._suffix,
                "comb": self._comb.get_combinations() if self._comb is not None else None,
            },
            "exec": self._execmd,
            "result": {
                "rc": self._rc,
                "state": str(self._state) if strstate else self._state,
                "time": self._exectime,
                "output": output,
            },
            "data": {
                "metrics": self._metrics,
                "tags": self._tags,
                "artifacts": self._artifacts,
            },
        }
        return res

    def to_minimal_json(self) -> dict[str, Any]:
        """
        Serialize minimal test information.

        :return: a JSON dict mapping the test.
        """
        return {
            "jid": self._jid,
            "invocation_cmd": self._invocation_cmd,
        }

    def from_minimal_json(self, jsonstr: str) -> None:
        """
        Import test object from minimal JSON.

        :param jsonstr: the imported json as raw str.
        """
        assert isinstance(jsonstr, str)
        jsonobj = json.loads(jsonstr)
        self._invocation_cmd = jsonobj.get("invocation_cmd", "exit 1")
        self._jid = jsonobj.get("jid", "-1")

    def from_json(self, test_json: dict[str, Any], filepath: str) -> None:
        """
        Import test object from full JSON.

        :param test_json: the json used to set this Test as dict.
        :param filepath: the path of the file the json come from.
        """
        assert isinstance(test_json, dict)
        self.res_scheme.validate(test_json, filepath)

        if "id" in test_json:
            self._jid = test_json["id"].get("jid", "")
            self._fq_name = test_json["id"].get("fq_name", "")
            self._te_name = test_json["id"].get("te_name", "")
            self._label = test_json["id"].get("label", "")
            self._subtree = test_json["id"].get("subtree", "")
            self._suffix = test_json["id"].get("suffix", "")
            comb_dict = test_json["id"].get("comb")
            self._comb = Combination({}, comb_dict, None) if comb_dict is not None else None

        self._execmd = test_json.get("exec", "")

        res = test_json.get("result", {})
        self._rc = res.get("rc", -1)
        self._state = TestState(res.get("state", TestState.ERR_OTHER))
        self._exectime = res.get("time", 0)
        self._output_info = res.get("output", {})
        self.b64_output = self._output_info.get("raw", "")

        if "data" in test_json:
            self._metrics = test_json["data"].get("metrics", {})
            self._tags = test_json["data"].get("tags", [])
            self._artifacts = test_json["data"].get("artifacts", {})

    def generate_script(self, srcfile: str) -> str:
        """
        Serialize test logic to its Shell representation.

        This script provides the shell sequence to put in a shell script
        switch-case, in order to reach that test from script arguments.

        :param srcfile: script filepath, to store the actual wrapped command.
        :return: the shell-compliant instruction set to build the test
        """
        pm_code = ""
        cd_code = ""
        env_code = ""
        cmd_code = ""

        self._invocation_cmd = "bash {} {}".format(srcfile, self._fq_name)

        # if changing directory is required by the test
        if self._cwd is not None:
            cd_code += "cd '{}'".format(shlex.quote(self._cwd))

        # manage package-manager deps
        for elt in self._mod_deps:
            pm_code += "\n".join([elt.get(load=True, install=True)])

        # manage environment variables defined in TE
        if self._testenv is not None:
            envs = []
            for e in self._testenv:
                k, v = e.split("=", 1)
                envs.append("{k}={v}; export {k}".format(k=shlex.quote(k), v=shlex.quote(v)))
            env_code = "\n".join(envs)

        cmd_code = self._execmd

        return """
        "{name}")
            {cd_code}
            pcvs_load={pm_code}
            pcvs_env={env_code}
            pcvs_cmd={cmd_code}
            ;;""".format(
            cmd_code="{}".format(shlex.quote(cmd_code)),
            env_code="{}".format(shlex.quote(env_code)),
            pm_code="{}".format(shlex.quote(pm_code)),
            cd_code=cd_code,
            name=self._fq_name,
        )

    @classmethod
    def compute_fq_name(
        cls,
        label: str,
        subtree: str,
        name: str,
        suffix: str | None = None,
        combination: str | None = None,
    ) -> str:
        """
        Generate the fully-qualified (dq) name for a test, based on:

        :param label: the label
        :param subtree: the subtree
        :param name: the TE name it is originated
        :param suffix: the extra suffix
        :param combination: the combination str.
        :return: The full qualified test name.
        """
        assert label
        assert subtree
        assert name
        path = os.path.normpath(os.path.join(label, subtree, name))
        return "_".join(filter(None, [path, suffix, combination]))

    def __repr__(self) -> str:
        return repr(self.__dict__)

    def __rich_repr__(self) -> Iterable[tuple[str, Any]]:
        return self.__dict__.items()


def generate_local_variables(label: str, subprefix: str) -> tuple[str, str, str, str]:
    """
    Return directories from PCVS working tree.

        - the base source directory
        - the current source directory
        - the base build directory
        - the current build directory

    :param label: name of the object used to generate paths
    :param subprefix: path to the subdirectories in the base path
    :return: paths for PCVS working tree
    """
    if subprefix is None:
        subprefix = ""

    base_srcdir = os.path.normpath(GlobalConfig.root["validation"]["dirs"].get(label, ""))
    cur_srcdir = os.path.normpath(os.path.join(base_srcdir, subprefix))
    base_buildir = os.path.normpath(
        os.path.join(GlobalConfig.root["validation"]["output"], "test_suite", label)
    )
    cur_buildir = os.path.normpath(os.path.join(base_buildir, subprefix))
    io.console.nodebug(
        f"src_dir: {base_srcdir}/{{{subprefix}}}, buildir: {base_buildir}/{{{subprefix}}}"
    )
    return base_srcdir, cur_srcdir, base_buildir, cur_buildir
