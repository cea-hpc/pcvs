
import random
import base64
import os
import json
import yaml
import jsonschema

prefix = os.path.join(os.getcwd(), "outputs")
labels = ["proj"+str(i) for i in range(0, 20+1)]
tagset1 = ["MPI", "OpenMP", "reproducers", "Threads"]
tagset2 = ["fast", "slow", "large", "small"]
random.seed()
if not os.path.isdir(prefix):
    os.makedirs(prefix)

file_count = random.randint(1, 100)
print("building {} files...".format(file_count))

with open(os.path.join(os.getcwd(), "pcvs-result-scheme.yaml"), 'r') as fh:
    scheme = yaml.safe_load(fh)

for f in range(1, file_count+1):
    filepath = os.path.join(prefix, "output-" + str(f) + "-list_of_tests.xml.json")
    warn_threshold = random.randint(30,90+1)
    err_threshold = random.randint(50,100+1)

    print("* Building {} ({}/{})".format(filepath, warn_threshold, err_threshold))
    
    if os.path.isfile(filepath):
        continue
    
    test_count = random.randint(1, 5000)
    json_node = {"tests" : []}

    
    for t in range(1, test_count+1):
        label = labels[random.randrange(0, len(labels))]
        tags = [tagset1[random.randrange(0, len(tagset1))]]
        tags += [tagset2[random.randrange(0, len(tagset2))]]
        
        # compil' election ? 
        if (random.randint(0,100) >= 90):
            tags.append('compilation')
    
        status = random.randint(0, 100)
        if status < warn_threshold:
            status = "success"
        elif warn_threshold < status  and status < err_threshold:
            status = "warn"
        else:
            status = "failure"
        
        time = random.randrange(0, 5000) / 1000
        output = base64.b64encode(("Test Sample {}".format(t)).encode('ascii')).decode('ascii')
        
        json_node['tests'].append({
            "command": "pcvs exec 'test_name'",
            "label": label,
            "subtree": " ",
            "name" : "test_{}".format(t),
            "full_name": label + " " + "test_{}".format(t),
            "result": {
                "output": output,
                "status": status,
                "time": time
            },
            "tags": tags

        })
    
    with open(filepath, 'w') as fh:
        json.dump(json_node, fh)
    


