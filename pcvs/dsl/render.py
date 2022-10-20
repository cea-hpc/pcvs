from matplotlib import pyplot as plt

from pcvs.dsl import Bank
from pcvs.dsl.analysis import SimpleAnalysis
from pcvs.testing.test import Test


def generate_serie_trend(res, out):
    x = []
    total = []
    succ = []
    fail = []
    other = []

    for e in res:
        nb = sum(e['cnt'].values())
        total.append(nb)
        succ.append(e['cnt'][str(Test.State.SUCCESS)])
        fail.append(e['cnt'][str(Test.State.FAILURE)])
        other.append(nb - e['cnt'][str(Test.State.SUCCESS)
                                   ] - e['cnt'][str(Test.State.FAILURE)])

    x = [e['date'] for e in res]
    total = [e['cnt'][str(Test.State.SUCCESS)] for e in res]
    succ = [e['cnt'][str(Test.State.SUCCESS)] for e in res]
    fail = [e['cnt'][str(Test.State.FAILURE)] for e in res]
    other = [e['cnt'][str(Test.State.FAILURE)] for e in res]

    plt.stackplot(x, fail, succ, labels=[
                  "FAILURE", "SUCCESS"], colors=['red', 'green'])
    plt.legend()
    plt.savefig(fname=out)
