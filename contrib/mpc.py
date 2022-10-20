import math

from pcvs.plugins import Plugin


class MyPlugin(Plugin):
    step = Plugin.Step.TEST_EVAL
    
    def run(self, *args, **kwargs):
        # this dict maps keys (it name) with values (it value)
        # returns True if the combination should be used
        config = kwargs['config']
        nb_nodes = config.machine.get('nodes', 1)
        nb_cores = config.machine.get('cores_per_node', 1)

        comb = kwargs['combination']
        n_node = comb.get('n_node', 1)
        n_proc = comb.get('n_proc', None)
        n_mpi = comb.get('n_mpi', None)
        n_core = comb.get('n_core', None)
        n_omp = comb.get('n_omp', None)
        net = comb.get('net', None)
        sched = comb.get('sched', None)

        if n_mpi is None:
            n_mpi = n_proc if n_proc is not None else n_node

        if n_proc is None:
            n_proc = n_mpi if n_mpi is not None else n_node


        if \
            (n_node > nb_nodes) or \
            (n_node > n_proc) or \
            (n_proc > n_mpi) or \
            (n_core is not None and n_core > 1 and n_core > (nb_cores * n_node) / n_proc) or \
            (net is not None and n_node > 1 and net == "shmem"):
                return False
        else:
            return True
