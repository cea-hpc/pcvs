import logging
import utils


class TEDescriptor:
    def __init__(self, node):
        if not isinstance(node, dict):
            logging.critical(
                "Unable to build a TestDescription "
                "from the given node (got %s)",
                type(node))
            raise utils.abort()
        pass


if __name__ == '__main__':
    test = TEDescriptor(4)
    pass
