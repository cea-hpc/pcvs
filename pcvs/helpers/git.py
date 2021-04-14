import getpass
import socket

import pygit2


def request_git_attr(k):
    git_conf = pygit2.Config.get_global_config()
    if k in git_conf:
        return git_conf[k]
    return None

def generate_data_hash(data):
    return str(pygit2.hash(data))

def get_current_username():
    u = request_git_attr('user.name')
    if u is None:
        return getpass.getuser()
    else:
        return u


def get_current_usermail():
    m = request_git_attr('user.email')
    if m is None:
        return "{}@{}".format(get_current_username(), socket.getfqdn())
    else:
        return m