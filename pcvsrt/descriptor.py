from pcvsrt import logs
import pcvsrt.descriptor
import yaml


class TEDescriptor(yaml.YAMLObject):
    def __init__(self, node, name):
        if not isinstance(node, dict):
            logs.err(
                "Unable to build a TestDescription "
                "from the given node (got {})".format(type(node)), abort=1)
        self._node = node
        self._name = name

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return repr(self._node)


if __name__ == '__main__':
    test = TEDescriptor(4)
    pass
