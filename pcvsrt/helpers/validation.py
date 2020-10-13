import jsonschema
import os
import yaml

import pcvsrt
from pcvsrt.helpers import log


class ValidationScheme:
    def __init__(self, prefix):
        self._prefix = prefix
        pass

    def validate(self, content, fail_on_error=True):
        with open(os.path.join(
                pcvsrt.ROOTPATH,
                'schemes/{}-scheme.yml'.format(self._prefix)
        ), 'r') as fh:
            try:
                schema = yaml.load(fh, Loader=yaml.FullLoader)
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
