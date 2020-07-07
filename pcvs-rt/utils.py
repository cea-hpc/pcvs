import sys
import logging


def abort():
    logging.critical("Due to error(s) above, PCVS is now gonna stop.")
    sys.exit(42)


if __name__ == '__main__':
    abort()
