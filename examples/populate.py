from pcvs.dsl import Bank, Serie, Run
from pcvs.testing.test import Test
from random_word import RandomWords
from random import randint
from itertools import product
MAX = 100
group = ["MPI", "OpenMP", "Others"]
sub = ["raw", "coll", "pt2pt", "directives", "io"]
rnd = RandomWords()
words = rnd.get_random_words()
tests = ["_".join(elt).replace(" ", "-") for elt in product(words, words)]

# open a bank

bank = Bank('./demo.git')
if 'mpc/b6ffe2123be606eab75f75b7dec00eba7d943461' not in bank.list_series():
    bank.new_serie("mpc/b6ffe2123be606eab75f75b7dec00eba7d943461")
serie = bank.get_serie("mpc/b6ffe2123be606eab75f75b7dec00eba7d943461")

thr = 100
for i in range(0, MAX):
    r = Run(serie)
    d = {}
    cnt_succ = 0
    cnt_fail = 0
    
    thr = thr / (1 + i/MAX)
    
    for idx, name in enumerate(tests):
        label = "SAMPLED"
        short_name = name
        subtree = '{}/{}'.format(group[idx % len(group)], sub[idx % len(sub)])
        long_name = "{}/{}/{}".format(label, subtree, short_name)
        
        n = randint(0, 100)
        
        print(thr, n)
        state = Test.State.SUCCESS if n > thr else Test.State.FAILURE
        
        cnt_succ += 1 if state == Test.State.SUCCESS else 0
        cnt_fail += 1 if state == Test.State.FAILURE else 0
        
        d[long_name] = {
            "id": {
                "te_name": short_name,
                "label": label,
                "subtree": subtree,
                "fq_name": long_name,
                "comb": {
                    "n_nreg": i, "n_test": idx,
                }
            },
            "exec": "./run this_program",
            "result": {
                "rc": 0,
                "output": "RmFrZSBleGVjdXRpb24=",
                "state": state,
                "time": 10.34
            },
        }
        
    r.update_flatdict(d)
    serie.commit(r, metadata={'cnt': {str(Test.State.SUCCESS): cnt_succ, str(Test.State.FAILURE): cnt_fail}})