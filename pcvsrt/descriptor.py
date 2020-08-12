from pcvsrt import logs
import pcvsrt.descriptor
import yaml

def unroll_numeric_values(array):
    for entry in array:
        if not isinstance(entry, str):
            logs.warn("Unable to deal with non-scalar iterator values; skip {}".format(entry))
        else:
            logs.warn("TODO unrooling numeric values")
    return array


def unroll_sequence(x):
    return x


class TEDescriptor(yaml.YAMLObject):
    def __init__(self, node, name):
        if not isinstance(node, dict):
            logs.err(
                "Unable to build a TestDescription "
                "from the given node (got {})".format(type(node)), abort=1)
        self._node = node
        self._name = name
        self._criterion = {}

    @property
    def name(self):
        return self._name

    def unroll_iterators(self, sys_iterators):
        if 'iterate' not in self._node.keys():
            return

        te_it = self._node['iterate']
        for k_it, v_redefine in te_it.items():
            # special case: 'program' it
            if 'program' == k_it:
                logs.warn("TODO: handle custom program iterators")
            elif k_it not in sys_iterators.keys():
                logs.warn("criterion '{}' not found. Discard".format(k_it))
            else:
                values = unroll_sequence(v_redefine['values'])
                # intereset values set
                final_set = set(values) | sys_iterators[k_it]['values']
                if not final_set:
                    logs.warn("No valid intersection found for '{}, Discard".format(k_it))
                else:
                    self._criterion[k_it] = (final_set)


    def __repr__(self):
        return repr(self._node)
