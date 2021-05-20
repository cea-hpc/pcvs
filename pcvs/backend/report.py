import json
import os

from pcvs.helpers.exceptions import ValidationException
from pcvs.helpers.system import ValidationScheme
from pcvs.testing.test import Test
from pcvs.webview import create_app


def locate_json_files(path):
    """Locate where json files are stored under the given prefix.

    :param path: [description]
    :type path: [type]
    :return: [description]
    :rtype: [type]
    """
    array = list()
    for f in os.listdir(path):
        if f.startswith("pcvs_rawdat") and f.endswith(".json"):
            array.append(os.path.join(path, f))

    return array


def build_data_tree(path=os.getcwd(), files=None):
    """Build the whole static data tree, browsed by Flask upon request.

    The tree is duplicated into three sections:
        * tests are gathered by labels
        * tests are gathered by tags
        * tests are gathered by status

    :param path: where build dir is located, defaults to os.getcwd()
    :type path: str, optional
    :param files: list of result files, defaults to None
    :type files: list, optional
    :return: the global tree
    :rtype: dict
    """
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
                    # scheme.validate(test)

                except ValidationException.FormatError:
                    print("\t- skip {} (bad formatting)".format(f))
                    continue

                cnt_tests += 1
                test_label = test['id'].get('label', "NOLABEL")
                test_tags = test['data'].get('tags', [])
                state = test['result'].get('state', Test.State.ERR_OTHER)
                test_status = str(Test.State(state))

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
                            str(Test.State.WAITING): 0,
                            str(Test.State.IN_PROGRESS): 0,
                            str(Test.State.SUCCEED): 0,
                            str(Test.State.FAILED): 0,
                            str(Test.State.ERR_DEP): 0,
                            str(Test.State.ERR_OTHER): 0,
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
                                str(Test.State.WAITING): 0,
                                str(Test.State.IN_PROGRESS): 0,
                                str(Test.State.SUCCEED): 0,
                                str(Test.State.FAILED): 0,
                                str(Test.State.ERR_DEP): 0,
                                str(Test.State.ERR_OTHER): 0,
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
    """Init the report interface.

    Start the Flask application after processing result files.

    :param path: where result files are stored (under 'rawdata' dir)
    :type path: str
    """
    print("Load YAML files")
    json_files = [os.path.join(path, f) for f in os.listdir(
        path) if f.startswith("pcvs_rawdat") and f.endswith(".json")]
    print("Build global tree ({} files)".format(len(json_files)))
    global_tree = build_data_tree(path, json_files)
    create_app(global_tree).run(host='0.0.0.0')
