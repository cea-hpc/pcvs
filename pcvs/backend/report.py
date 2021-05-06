import json
import os
from pcvs.helpers.exceptions import ValidationException

from pcvs.testing.test import Test
from pcvs.webview import create_app
from pcvs.helpers.system import ValidationScheme

def locate_json_files(path):
    array = list()
    for f in os.listdir(path):
        if f.startswith("pcvs_rawdat") and f.endswith(".json"):
            array.append(os.path.join(path, f))

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
    scheme = ValidationScheme("test-result")

    # with open(os.path.join(os.getcwd(), "result-scheme.yml"), "r") as fh:
    #    val_str = yaml.safe_load(fh)

    for idx, f in enumerate(files):
        print("Dealing with n°{}".format(idx+1))
        with open(f, 'r') as fh:
            stream = json.load(fh)
            # TODO: read & store metadata
            for test in stream.get('tests', []):
                try:
                    pass
                    # veeeeery slow
                    #scheme.validate(test)
                    
                except ValidationException.FormatError:
                    print("\t- skip {} (bad formatting)".format(f))
                    continue
            
                cnt_tests += 1
                test_label = test['id'].get('label', "NOLABEL")
                test_tags = test['data'].get('tags', [])
                test_status = str(test['result'].get('state', Test.STATE_OTHER))

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
                            str(Test.STATE_OTHER): 0,
                            str(Test.STATE_SUCCEED): 0,
                            str(Test.STATE_FAILED): 0,
                            str(Test.STATE_INVALID_SPEC): 0,
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
                               str(Test.STATE_OTHER): 0,
                            str(Test.STATE_SUCCEED): 0,
                            str(Test.STATE_FAILED): 0,
                            str(Test.STATE_INVALID_SPEC): 0,
                            "total": 0
                            }
                        }
                    })
                    tags[tag]['tests'].append(test)
                    tags[tag]["metadata"]["count"][test_status] += 1
                    tags[tag]["metadata"]["count"]["total"] += 1
    global_tree['metadata'] = {
        "rootdir": path,
        "count": {
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

