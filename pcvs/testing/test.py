import base64
import os
import shlex
from enum import IntEnum

from pcvs import PATH_INSTDIR
from pcvs.helpers import log
from pcvs.helpers.pm import PManager


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
        WAITING = 0
        IN_PROGRESS = 1
        SUCCEED = 2
        FAILED = 3
        ERR_DEP = 4
        ERR_OTHER = 5

        def __str__(self):
            return self.name
        
        def __repr__(self):
            return (self.name, self.value)


    """A basic test representation, from one step to concretize the logic
    to the JCHRONOSS input datastruct."""
    def __init__(self, **kwargs):
        """register a new test"""
        self._array = kwargs
        self._rc = 0
        self._time = 0.0
        self._out = None
        self._state = Test.State.WAITING
        
        if 'dep' in self._array:
            deparray = self._array['dep']
            self._array['dep'] = {k: None for k in deparray}
    
    def override_cmd(self, cmd):
        self._array['command'] = cmd
    
    @property
    def name(self):
        return self._array['name']

    @property
    def command(self):
        return self._array['command']
    
    @property
    def wrapped_command(self):
        return self._array['wrapped_command']

    @property
    def deps(self):
        return self._array["dep"]

    def set_dep(self, name, obj):
        assert(name in self._array['dep'])
        self._array['dep'][name] = obj
        
    def is_pickable(self):
        return not self.been_executed() and len([d for d in self.deps.values() if not d.been_executed()]) == 0
    
    def has_failed_dep(self):
        return len([d for d in self.deps.values() if d.state == Test.State.FAILED]) > 0
    
    def first_valid_dep(self):
        for d in self.deps.values():
            if not d.been_executed():
                return d
    
    @property
    def timeout(self):
        if self._array['time'] is None:
            return None
        return self._array['time'] + self._array['delta']
        
    def get_dim(self, unit="n_node"):
        return self._array['nb_res']

    def save_final_result(self, rc=0, time=0.0, out=b'', state=None):
        
        if state is None:
            state = Test.State.SUCCEED if self._rc == rc else Test.State.FAILED
        self.executed(state)
        self._rc = rc
        self._out = base64.b64encode(out).decode('ascii')
        self._time = time
        
        for elt_k, elt_v in self._array['artifacts'].items():
            if os.path.isfile(elt_v):
                with open(elt_v, 'rb') as fh:
                    self._array['artifacts'][elt_k] = base64.b64encode(fh.read()).decode("ascii")

    def display(self):
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
    

        log.manager.print_job(label, self._time, self.name, colorname=colorname, icon=icon)
        if self._out:
            if (log.manager.has_verb_level("info") and self.state == Test.State.FAILED) or log.manager.has_verb_level("debug"):
                log.manager.print(base64.b64decode(self._out))

    def executed(self, state=None):
        self._state = state if type(state) == Test.State else Test.State.FAILED

    def been_executed(self):
        return self._state not in [Test.State.WAITING, Test.State.IN_PROGRESS]
    
    def picked(self):
        self._state == Test.State.IN_PROGRESS
            
    @property
    def state(self):
        return self._state
    
    def to_json(self):
        return {
            "id" : {
                "te_name": self._array["te_name"],
                "label" : self._array["label"],
                "subtree" : self._array["subtree"],
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
        """Serialize test logic to its Shell representation"""
        pm_code = ""
        cd_code = ""
        env_code = ""
        cmd_code = ""
        post_code = ""
        
        self._array['wrapped_command'] = 'sh {} {}'.format(srcfile, self._array['name'])
        
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
                env_code += "{}; export {}\n".format(shlex.quote(e), shlex.quote(e.split('=')[0]))

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
