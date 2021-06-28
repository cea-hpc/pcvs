from pcvs.plugins import Plugin
from pcvs.helpers import log
from pcvs.orchestration.set import Set

class PickRandomJobs(Plugin):
    step = Plugin.Step.INVALID

    def run(self, *args, **kwargs):
        joblist = []
        jobman = kwargs['jobman']

        for dim in range(jobman.nb_dims, 0, -1):
            per_res_list = jobman.get_dim(dim)
            job = per_res_list.pop()

            #TODO:
            joblist.append(job)
            break

        if len(joblist) > 0:
            s = Set()
            s.add(joblist)
            return s

        return None
