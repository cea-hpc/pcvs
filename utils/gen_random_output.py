
import base64
import json
import os
import random

import jsonschema
import yaml

file_count = 9000
test_count = 1000000
test_per_file = int(test_count/file_count)
prefix = os.path.join(os.getcwd(), "rawdata")
labels = ["proj"+str(i) for i in range(0, 20+1)]
tagset1 = ["MPI", "OpenMP", "reproducers", "Threads"]
tagset2 = ["fast", "slow", "large", "small"]
random.seed()
if not os.path.isdir(prefix):
    os.makedirs(prefix)

print("building {} files...".format(file_count))

for f in range(0, file_count):
    filepath = os.path.join(prefix, "pcvs_rawdat{:04}.json".format(f))
    warn_threshold = random.randint(30,90+1)
    err_threshold = random.randint(50,100+1)

    print("* Building {} ({}/{})".format(filepath, warn_threshold, err_threshold))
    
    if os.path.isfile(filepath):
        continue
    
    json_node = {"tests" : []}

    for t in range(1, test_per_file+1):
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
        output = base64.b64encode(("Test Sample {}".format(t)).encode('ascii')).decode('ascii')
        
        json_node['tests'].append({
            "id": {
                "label": label,
                "subtree": "sub",
                "te_name" : "test_{}".format(t),
                "full_name": "{}/{}/test_{}".format(label, "sub", t),
                "comb": {
                    "n_mpi": f
                }
            },
            "exec": "sh list_of_tests.sh '{}'".format("{}/{}/test_{}".format(label, "sub", t)),
            "result": {
                "rc": random.randint(0, 1),
                "output": output,
                "state": status,
                "time": time
            },
            "data": {
                "tags": tags,
                "artifacts": {
                    "this_is_a_test.txt": "dGhlIHRlc3Qgd29ya2VkCg=="}
            }
        })
    
    with open(filepath, 'w') as fh:
        json.dump(json_node, fh)
    


