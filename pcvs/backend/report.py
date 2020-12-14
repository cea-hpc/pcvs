import json
import os
import pprint

import jsonschema
import yaml

from pcvs.webview import create_app


def locate_json_files(path):
    array = list()
    for root, _, files in os.walk(path):
        for f in files:
            if f.startswith("output-") and f.endswith(".xml.json"):
                array.append(os.path.join(root, f))
        
    return array


def build_data_tree(path=os.getcwd(), files=None):
    global_tree = {
        "metadata": {},
        "label": {},
        "tag": {},
        "status": {}
    }
    labels = global_tree["label"]
    tags = global_tree["tag"]
    statuses = global_tree["status"]
    cnt_tests = 0
    
    #with open(os.path.join(os.getcwd(), "result-scheme.yml"), "r") as fh:
    #    val_str = yaml.load(fh, Loader=yaml.FullLoader)
    
    for idx, f in enumerate(files):
        print("Dealing with n°{}".format(idx+1))
        with open(f, 'r') as fh:
            stream = json.load(fh)
            #try:
            #	jsonschema.validate(instance=stream, schema=val_str)
            #except jsonschema.exceptions.ValidationError as e:
            #	print("skip {} (bad formatting): {}".format(f, e))
            #	continue
            #TODO: read & store metadata
            for test in stream.get('tests', []):
                cnt_tests += 1
                test_label = test.get('label', 'NOLABEL')
                test_tags = test.get('tags', [])
                test_status = test['result'].get('status', 'error')

                statuses.setdefault(test_status, {
                    "tests": list(),
                    "metadata": {
                        "count": 0
                    }
                })
                statuses[test_status]["tests"].append(test)
                statuses[test_status]['metadata']['count'] += 1
                
                # Per-label
                labels.setdefault(test_label, {
                    "tests": list(),
                    "metadata": {
                        "count": {
                            "error": 0,
                            "success": 0,
                            "failure": 0,
                            "warn": 0,
                            "total": 0
                        }
                    }
                })
                labels[test_label]['metadata']["count"][test_status] += 1
                labels[test_label]['metadata']["count"]['total'] += 1
                labels[test_label]["tests"].append(test)
                
                for tag in test_tags:
                    tags.setdefault(tag, {
                        "tests": list(),
                        "metadata": {
                            "count": {
                                "error": 0,
                                "success": 0,
                                "failure": 0,
                                "warn": 0,
                                "total": 0
                            }
                        }
                    })
                    tags[tag]['tests'].append(test)
                    tags[tag]["metadata"]["count"][test_status] += 1
                    tags[tag]["metadata"]["count"]["total"] += 1
    global_tree['metadata'] = {
        "rootdir": path,
        "count" : {
            "tests": cnt_tests,
            "labels": len(labels.keys()),
            "tags": len(tags.keys()),
            "files": len(files)
        }
    }
    return global_tree

def webview_run_server(path):
    print("Load YAML files")
    json_files = locate_json_files(path)
    print("Build global tree ({} files)".format(len(json_files)))
    global_tree = build_data_tree(path, json_files)
    create_app(global_tree).run(host='0.0.0.0')