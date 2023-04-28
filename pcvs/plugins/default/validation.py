from pcvs.backend import bank
from pcvs.helpers.system import MetaConfig
from pcvs.plugins import Plugin
from pcvs.testing.test import Test


class BankValidationPlugin(Plugin):
    """TODO:
    """
    step = Plugin.Step.TEST_RESULT_EVAL

    def __init__(self):
        super().__init__()
        self._bank_hdl = None

    def run(self, *args, **kwargs):
        """TODO:
        """
        if not self._bank_hdl:
            bankname = MetaConfig.root.validation.get('target_bank', None)
            if not bankname:
                return None

            self._bank_hdl = bank.Bank(path=None, token=bankname)
            self._bank_hdl.connect()
        self._serie = self._bank_hdl.get_serie(
            self._bank_hdl.build_target_branch_name(hash=MetaConfig.root.validation.pf_hash))
        if not self._serie:
            # no history, stop !
            return None

        node = kwargs.get('analysis', {})
        job = kwargs.get('job', None)

        method = node.get('method', None)
        args = node.get('args', {})
        if method and hasattr(self, method):
            func = getattr(self, method)
            return func(args, job)
        return None

    def not_longer_than_previous_runs(self, args, job):
        """TODO:
        """
        if not self._bank_hdl:
            return Test.State.ERR_OTHER

        max_runs = args.get('history_depth', 1)
        tolerance = args.get('tolerance', 0)
        sum = 0
        cnt = 0
        run = self._serie.last
        while cnt < max_runs:
            res = run.get_data(job.name)
            if res and res.state == Test.State.SUCCESS:
                sum += res.time
                cnt += 1
            run = run.previous
            if run is None:
                break
        if cnt >= 0 and job.time >= (sum / cnt) * (1 + tolerance/100):
            return Test.State.FAILURE
        else:
            return Test.State.SUCCESS
