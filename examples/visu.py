from pcvs.dsl import Bank
from pcvs.testing.test import Test
from pcvs.dsl.analysis import SimpleAnalysis
from matplotlib import pyplot as plt

bank = Bank('demo.git')
a = SimpleAnalysis(bank)

l = bank.list_series()
import time
s = time.time()
data = a.generate_weighted_divergence(l[1].name)
e = time.time()
print("Took {} sec(s)".format(float(e-s))
data = a.generate_serie_trend(l[1].name)

x = []
total = []
succ = []
fail = []
other = []

for e in data:
    nb = sum(e['cnt'].values())
    total.append(nb)
    succ.append(e['cnt'][str(Test.State.SUCCESS)])
    fail.append(e['cnt'][str(Test.State.FAILURE)])
    other.append(nb - e['cnt'][str(Test.State.SUCCESS)] - e['cnt'][str(Test.State.FAILURE)])
    

x = [e['date'] for e in data]
total = [e['cnt'][str(Test.State.SUCCESS)] for e in data]
succ = [e['cnt'][str(Test.State.SUCCESS)] for e in data]
fail = [e['cnt'][str(Test.State.FAILURE)] for e in data]
other = [e['cnt'][str(Test.State.FAILURE)] for e in data]

plt.stackplot(x, fail, succ, labels=["FAILURE", "SUCCESS"], colors=['red', 'green'])
plt.legend()
plt.show()