import subprocess
import queue
import time
import os
import signal
import threading
import json

import pcvs
from pcvs.testing.test import Test
from pcvs import io
from pcvs.helpers.exceptions import RunnerException
from pcvs.orchestration.publishers import BuildDirectoryManager
from pcvs.orchestration.set import Set
from pcvs.helpers.system import MetaConfig


class RunnerAdapter(threading.Thread):
    sched_in_progress = True
    def __init__(self, buildir, context=None, ready=None, complete=None, *args, **kwargs):
        self._prefix = buildir
        self._ctx = context
        self._rq = ready
        self._cq = complete
        
        super().__init__()

    def run(self):
        while True:
            try:
                if self.sched_in_progress:
                    item = self._rq.get(block=False, timeout=5)
                    self.execute_set(item)
                    self._cq.put(item)
                else:
                    break
            except queue.Empty:
                continue
            except Exception as e:
                raise e

    def execute_set(self, set):
        if set.execmode == Set.ExecMode.LOCAL:
            return self.local_exec(set)
        else:
            return self.remote_exec(set)
    
    def local_exec(self, set) -> None:
        """Execute the Set and jobs within it.

        :raises Exception: Something occured while running a test"""
        io.console.debug('{}: [LOCAL] Set start'.format(self.ident))
        for job in set.content:
            try:
                p = subprocess.Popen('{}'.format(job.invocation_command),
                                     shell=True,
                                     stderr=subprocess.STDOUT,
                                     stdout=subprocess.PIPE,
                                     start_new_session=True)
                start = time.time()
                stdout, _ = p.communicate(timeout=job.timeout)
                final = time.time() - start
                
                # Note: The return code here is coming from the script,
                # not the test itself. It is transitively transmitted once the
                # test complete, except if test used matchers to validate.
                # in that case, a non-zero exit code indicates at least one
                # matcher failed.
                # The the engine, no other checks than return code evaluation
                # is necessary to assess test status.
                rc = p.returncode

            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                stdout, _ = p.communicate()
                rc = Test.Timeout_RC  # nah, to be changed
                final = job.timeout
            except Exception:
                raise
            job.save_raw_run(time=final, rc=rc, out=stdout)
            job.save_status(Test.State.EXECUTED)
        set.complete = True

    def remote_exec(self, set: Set) -> None:
        jobman_cfg = {}
        if set.execmode == Set.ExecMode.ALLOC:
            jobman_cfg = MetaConfig.root.machine.job_manager.allocate
        elif set.execmode == Set.ExecMode.REMOTE:
            jobman_cfg = MetaConfig.root.machine.job_manager.remote
        elif set.execmode == Set.ExecMode.BATCH:
            jobman_cfg = MetaConfig.root.machine.job_manager.batch

        parallel = MetaConfig.root.validation.scheduling.get("parallel", 1)
        
        #TODO: Prepare exec context
        wrapper = jobman_cfg.get('wrapper', "")
        env = os.environ.copy()
        ctx_path = os.path.join(self._prefix, pcvs.NAME_BUILD_CONTEXTDIR, str(set.id))
        os.makedirs(ctx_path)
        updated_env = {"PCVS_JOB_MANAGER_{}".format(i.upper()): jobman_cfg[i] for i in ['program', 'args'] if i in jobman_cfg}
        updated_env['PCVS_SET_DIM'] = str(set.dim)
        updated_env['PCVS_SET_CMD'] = jobman_cfg.program if jobman_cfg.program else ""
        updated_env['PCVS_SET_CMD_ARGS'] = jobman_cfg.args if jobman_cfg.args else ""
        env.update(updated_env)
        
        cmd = "{script} pcvs remote-run -c {ctx} -p {parallel}".format(
            script=wrapper,
            ctx=ctx_path,
            parallel=parallel
        )
        try:
            ctx = RemoteContext(ctx_path)
            ctx.save_input_to_disk(set)
            assert(ctx.check_input_avail())
            self._process_hdl = subprocess.Popen(cmd, shell=True, env=env,
                                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = self._process_hdl.communicate()
            if err:
                io.console.warning("Set {} - error output: {}".format(set.id, err.decode('utf-8')))
            if ctx.check_output_avail():
                ctx.load_result_from_disk(set)
            else:
                io.console.warning("Set {} did not produce any output".format(set.id))
        except:
            raise RunnerException.LaunchError(
                reason="Fail to start a remote Runner",
                dbg_info={'cmd': cmd})


def progress_jobs(q, ctx, ev):
    local_cnt = 0
    while local_cnt < ctx.cnt:
        try:
            item = q.get(block=False, timeout=5)
            for job in item.content:
                ctx.save_result_to_disk(job)
                local_cnt += 1
        except queue.Empty:
            continue
        except Exception as e:
            raise e
    ev.set()

class RunnerRemote:
    
    def __init__(self, ctx_path):
        self._ctx_path = ctx_path
    
    def connect_to_context(self):
        self._ctx = RemoteContext(self._ctx_path)
        self._set = self._ctx.load_input_from_disk()
    
    def run(self, parallel=1):
        
        self._ctx.mark_as_not_completed()
        thr_list = list()
        rq = queue.Queue()
        pq = queue.Queue()
        ev = threading.Event()
        
        progress = threading.Thread(target=progress_jobs, args=(pq, self._ctx, ev))
        progress.start()
        
        for _ in range(0, parallel):
            thr = RunnerAdapter(self._ctx_path, ready=rq, complete=pq)
            thr.start()
            thr_list.append(thr)
        
        for job in self._set.content:
            s = Set(execmode=Set.ExecMode.LOCAL)
            s.add(job)
            rq.put(s)
        
        while not ev.is_set():
            time.sleep(1)
        
        RunnerAdapter.sched_in_progress = False
        for thr in thr_list:
            thr.join()
        self._ctx.mark_as_completed()


class RemoteContext:
    
    MAGIC_TOKEN = "PCVS-MAGIC"
    
    def __init__(self, prefix, set=None):
        self._path = prefix
        self._cnt = 0
        
        if set:
            self._path = os.path.join(self._path, str(set.id))
        self._completed_file = os.path.join(prefix, ".completed")

        if set:
            self.save_input_to_disk(set)

        #inputs are flushed atomically, no need for a file handler
        #outputs are stored incrementally to avoid data losses
        self._outfile = None
        
    @property
    def cnt(self):
        return self._cnt

    def save_input_to_disk(self, set):
        with open(os.path.join(self._path, "input.json"), "w") as f:
            f.write(json.dumps(list(map(lambda x: x.to_minimal_json(), set.content))))

    def check_input_avail(self):
        f = os.path.join(self._path, "input.json")
        return os.path.isfile(f)

    def check_output_avail(self):
        f = os.path.join(self._path, "output.bin")
        return os.path.isfile(f)

    def load_input_from_disk(self):
        assert(os.path.isdir(os.path.join(self._path)))
        set = Set(execmode=Set.ExecMode.LOCAL)
        with open(os.path.join(self._path, "input.json"), "r") as f:
            data = json.load(f)
            for job in data:
                cur = Test()
                cur.from_minimal_json(job)
                set.add(cur)
                self._cnt += 1
        return set
    
    def save_result_to_disk(self, job: Test):
        if not self._outfile:
            self._outfile = open(os.path.join(self._path, "output.bin"), 'wb')
        data = job.encoded_output
        self._outfile.writelines([
            "{}:{}:{}:{}:{}\n".format(self.MAGIC_TOKEN, job.jid, len(data), job.time, job.retcode).encode("utf-8"),
            data,
            "\n".encode('utf-8')
            ])
        
    def load_result_from_disk(self, set):
        with open(os.path.join(self._path, "output.bin"), "rb") as fh:
            lines = fh.readlines()
            jobs = list(set.content)
            for lineum, linedata in enumerate(lines):
                if lineum % 2 == 0:
                    # metadata:
                    try:
                        magic, jobid, datalen, timexec, retcode = linedata.decode('utf-8').split(":")
                    except:
                        raise
                    assert(magic == self.MAGIC_TOKEN)
                    datalen = int(datalen)
                    timexec = float(timexec)
                    retcode = int(retcode)
                    data = b""
                    job: Test = set.find(jobid)
                    assert(job)
                    if datalen > 0:
                        data = lines[lineum+1].strip()
                        job.encoded_output = data
                    job.save_raw_run(rc=retcode, time=timexec)
                    job.save_status(Test.State.EXECUTED)

    def mark_as_completed(self):
        if self._outfile:
            self._outfile.close()
        open(self._completed_file, 'w').close()

    def mark_as_not_completed(self):
        if os.path.exists(self._completed_file):
            os.remove(self._completed_file)

    @property
    def completed(self):
        return os.path.exists(self._completed_file)