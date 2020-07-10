import sys
import os
import logging
import tempfile

FORMAT = "%(levelname)s(%(module)s): %(message)s"
logging.basicConfig(format=FORMAT)


def abort():
    logging.critical("Due to error(s) above, PCVS is now gonna stop.")
    sys.exit(42)


def log(*msg, func):
    for elt in msg:
        func(elt)


def debug(*msg):
    log(*msg, func=logging.debug)


def info(*msg):
    log(*msg, func=logging.info)


def warn(*msg):
    log(*msg, func=logging.warning)


def err(*msg):
    log(*msg, func=logging.error)
    abort()


def open_in_editor(filepath):
    # create a backup to make edition atomic
    os.system('{} {}'.format(os.getenv('EDITOR'), filepath))


if __name__ == '__main__':
    err("this is a bug", "I don't know")
