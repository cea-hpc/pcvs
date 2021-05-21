import getpass
import socket

import pygit2


def request_git_attr(k) -> str:
    """Get a git configuration.

    :param k: parameter to get
    :type k: str
    :return: a git configuration
    :rtype: str
    """
    try:
        # TODO: not only look for user config
        git_conf = pygit2.Config.get_global_config()
        if k in git_conf:
            return git_conf[k]
    except IOError:
        # to user config
        pass
    return None


def generate_data_hash(data) -> str:
    """Hash data with git protocol.

    :param data: data to hash
    :type data: str
    :return: hashed data
    :rtype: str
    """
    return str(pygit2.hash(data))


def get_current_username() -> str:
    """Get the git username.

    :return: git username
    :rtype: str
    """
    u = request_git_attr('user.name')
    if u is None:
        return getpass.getuser()
    else:
        return u


def get_current_usermail():
    """Get the git user mail.

    :return: git user mail
    :rtype: str
    """
    m = request_git_attr('user.email')
    if m is None:
        return "{}@{}".format(get_current_username(), socket.getfqdn())
    else:
        return m
