
import base64
import json
import os
import random
from rich.progress import track
import shutil
from pcvs.orchestration.publishers import BuildDirectoryManager
from pcvs.testing.test import Test

import jsonschema

test_count = 10000
prefix = os.path.join(os.getcwd(), "fake_build")
labels = ["proj"+str(i) for i in range(0, 20+1)]
tagset1 = ["MPI", "OpenMP", "reproducers", "Threads"]
tagset2 = ["fast", "slow", "large", "small"]
random.seed()

if os.path.isdir(prefix):
    shutil.rmtree(prefix)
os.makedirs(prefix)
manager = BuildDirectoryManager(build_dir=prefix)
warn_threshold = random.randint(30,90+1)
err_threshold = random.randint(50,100+1)

manager.init_results(per_file_max_sz=10*1024*1024)
manager.results.register_view_item(view="tags", item="MPI")

for t in track(range(1, test_count)):
    label = labels[random.randrange(0, len(labels))]
    tags = [tagset1[random.randrange(0, len(tagset1))]]
    tags += [tagset2[random.randrange(0, len(tagset2))]]

    # compil' election ? 
    if (random.randint(0,100) >= 90):
        tags.append('compilation')

    status = random.randint(0, 100)
    if status < warn_threshold:
        status = 1
    elif warn_threshold < status and status < err_threshold:
        status = 3
    else:
        status = 2

    time = random.randrange(0, 5000) / 1000
    output = "Test Sample {}".format(t).encode("utf-8")
    fqname = "{}/{}/test_{}".format(label, "sub", t)

    cur = Test(
        label=label,
        subtree="sub",
        te_name="test_{}".format(t),
        dim=random.randint(0,10),
        command="sh list_of_tests.sh '{}'".format("{}/{}/test_{}".format(label, "sub", t)),
        tags=tags
    )
    cur.save_final_result(
            rc=random.randint(0, 1),
            time=time,
            out=output
            )
    manager.results.save(cur)

manager.finalize()


