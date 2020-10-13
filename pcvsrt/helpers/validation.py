import jsonschema
import os
import json

import pcvsrt
from pcvsrt.helpers import io, log


class ValidationScheme:
    def __init__(self, prefix):
        self._prefix = prefix
        pass

    def validate(self, content, fail_on_error=True):
        with open(os.path.join(
                pcvsrt.ROOTPATH,
                'schemes/{}-scheme.json'.format(self._prefix)
        ), 'r') as fh:
            try:
                schema = json.load(fh)
                jsonschema.validate(instance=content, schema=schema)
            except jsonschema.ValidationError as e:
                if fail_on_error:
                    log.err("Wrong format for '{}':".format(self._prefix),
                            "{}".format(e))
                else:
                    raise e
            except Exception as e:
                log.err(
                    "Something wrong happen validating {}".format(self._prefix),
                    '{}'.format(e)
                )
