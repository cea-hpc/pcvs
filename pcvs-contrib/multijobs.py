from pcvs.plugins import Plugin
from pcvs.helpers import log
from pcvs.orchestration.set import Set

class PickRandomJobs(Plugin):
    step = Plugin.Step.SCHED_SET_EVAL

    def run(self, *args, **kwargs):
        joblist = []

        for dim in range(jobman.nb_dims, 0, -1):
            for per_res_list in jobman.get_dim(dim):
                job = per_res_list.pop()

                #TODO:

                joblist.append(job)

        if len(joblist) > 0:
            return Set(joblist)

        return None
