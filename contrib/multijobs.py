from pcvs.helpers import log
from pcvs.orchestration.set import Set
from pcvs.plugins import Plugin
from pcvs.testing.test import Test

class SchedMultiJobs(Plugin):
    step = Plugin.Step.SCHED_SET_EVAL

    first_run_with_compilation = True

    def first_allocation(self, jobman):
        the_set = None
        for dim in range(jobman.nb_dims, 0, -1):
            per_res_list = jobman.get_dim(dim)
            list_count = len(per_res_list)
            # avoid iterating & push/pop from the same list
            while list_count > 0:
                job = per_res_list.pop(0)
                list_count -= 1
                if "compilation" in job.tags:
                    if not the_set:
                        the_set = Set(execmode=Set.ExecMode.REMOTE)
                    the_set.add(job)
                    job.pick()
                else:
                    job.not_picked()
                    per_res_list.append(job)
        return the_set

    def run(self, *args, **kwargs):
        jobman = kwargs['jobman']

        if self.first_run_with_compilation:
            self.first_run_with_compilation = not self.first_run_with_compilation
            return self.first_allocation(jobman)
        else:
            the_set = None
            count = 0
            for dim in range(jobman.nb_dims, 0, -1):
                per_res_list = jobman.get_dim(dim)
                list_count = len(per_res_list)
                # avoid iterating & push/pop from the same list
                while list_count > 0:
                    job = per_res_list.pop(0)
                    list_count -= 1
                    if job.has_completed_deps():
                        if not the_set:
                            the_set = Set(execmode=Set.ExecMode.ALLOC)
                        the_set.add(job)
                        job.pick()
                        count += 1
                        if count >= 10:
                            break
                    else:
                        per_res_list.append(job)
            return the_set
