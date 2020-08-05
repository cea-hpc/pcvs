from pcvsrt import logs


class TEDescriptor:
    def __init__(self, node):
        if not isinstance(node, dict):
            logs.err(
                "Unable to build a TestDescription "
                "from the given node (got {})".format(type(node)), abort=1)


if __name__ == '__main__':
    test = TEDescriptor(4)
    pass
