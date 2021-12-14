import pcvs
import subprocess
from pcvs.helpers.criterion import Combination, Criterion, Serie
from pcvs.testing.test import Test
from pcvs.orchestration import Orchestrator

def parse_spec_variants(specname):
    d = dict()
    cmd = 'spack python -c \'import spack.repo; print("\\n".join(["{}:{}".format(v[0].name, v[0].allowed_values) for v in spack.repo.get("'+ specname +'").variants.values()]))\''
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    fds = p.communicate()
    for line in fds[0].decode().rstrip().split("\n"):
        name, val_raw = line.split(':')
        values = val_raw.split(', ')
        
        d[name] = Criterion(name, {
            "option": "{}=".format(name),
            "position": "after",
            "type": "argument",
            "subtitle": "{}=".format(name),
            "values": values
        }, local=True)
        
        d[name].concretize_value()
    return d

def generate_from_variants(package):
    tests = list()
    for c in Serie(parse_spec_variants(package)).generate():
        tests.append(Test(
                comb=c,
                te_name=package,
                label="SPACK",
                subtree="",
                command="spack install {} {}".format(package, " ".join(c.translate_to_command()[2])),
        ))

    return tests