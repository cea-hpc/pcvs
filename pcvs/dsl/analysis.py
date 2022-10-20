import json
from abc import ABC, abstractmethod

from pcvs.dsl import Job, Run, Serie
from pcvs.testing.test import Test


class BaseAnalysis(ABC):
    """TODO:
    """

    def __init__(self, bank):
        self._bank = bank


class SimpleAnalysis(BaseAnalysis):
    """TODO:
    """

    def __init__(self, bank):
        super().__init__(bank)

    def generate_serie_trend(self, serie, start=None, end=None):
        """TODO:
        """
        if not isinstance(serie, Serie):
            serie = self._bank.get_serie(serie)
        stats = []
        for run in serie.find(Serie.Request.RUNS, start, end):
            ci_meta = run.get_info()
            run_meta = run.get_metadata()
            stats.append({'date': ci_meta['date'], **run_meta})

        return stats

    def generate_weighted_divergence(self, serie, threshold=0, prefix=None):
        """TODO:
        """
        if not isinstance(serie, Serie):
            serie = self._bank.get_serie(serie)
        runs = serie.history()
        cnt = len(runs)
        stats = {Job.Trend(i): {} for i in range(len(Job.Trend))}
        for test in runs[0].tests:
            testname = test.name
            if prefix is not None and not testname.startswith(prefix):
                continue
            weight = 0
            latest = test.state
            div = Job.Trend.STABLE
            while weight < cnt and (weight < threshold or threshold == 0):
                other = runs[weight].get_data(testname)
                if other.state != latest:
                    if latest == Test.State.SUCCESS:
                        div = Job.Trend.PROGRESSION
                    elif other.state == Test.State.SUCCESS:
                        div = Job.Trend.REGRESSION
                    else:
                        # ERRs <-> FAILURES are considered failures here
                        div = Job.Trend.STABLE
                    break
                weight += 1
            stats[div][testname] = weight
        return stats


class ResolverAnalysis(BaseAnalysis):
    """TODO:
    """

    def __init__(self, bank):
        super().__init__(bank)
        self._data = None

    def fill(self, data):
        """TODO:
        """
        assert (isinstance(data, dict))
        self._data = data
