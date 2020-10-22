import jsonschema
import os
import yaml

import pcvsrt
from pcvsrt.helpers import log


class ValidationScheme:
    def __init__(self, name):
        self._prefix = name

        with open(os.path.join(
                            pcvsrt.ROOTPATH,
                            'schemes/{}-scheme.yml'.format(name)
                        ), 'r') as fh:
            self._scheme = yaml.load(fh, Loader=yaml.FullLoader)

    def validate(self, content, fail_on_error=True, filepath=None):
        try:
            if filepath is None:
                filepath = "'data stream'"
            
            jsonschema.validate(instance=content, schema=self._scheme)
        except jsonschema.exceptions.ValidationError as e:
            if fail_on_error:
                log.err("Wrong format: {} ('{}'):".format(
                                filepath,
                                self._prefix),
                        "{}".format(e.message))
            else:
                raise e
        except Exception as e:
            log.err(
                "Something wrong happen validating {}".format(self._prefix),
                '{}'.format(e)
            )
