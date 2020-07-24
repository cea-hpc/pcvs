import sys
import os
import click
import logging
import textwrap
from pcvsrt import globals

FORMAT = "%(levelname)s: %(message)s"
glyphs = {
    'copy': '(c)',
    'item': '*',
    'sec': '#',
    'hdr': '=',
    'star': '*',
    'fail': 'X',
    'succ': 'V',
    'git': '(git)',
    'time': '(time)',
}


def __set_logger(v):
    lv = None
    if v > 1:
        lv = logging.DEBUG
    elif v > 0:
        lv = logging.INFO
    else:
        lv = logging.WARNING

    logging.basicConfig(format=FORMAT, level=lv)


def __set_encoding(e):
    global glyphs
    if e and 'utf-' in sys.getdefaultencoding():
        glyphs['copy'] = '\u00A9'
        glyphs['item'] = '\u27E2'
        glyphs['sec'] = '\u2756'
        glyphs['hdr'] = '\u23BC'
        glyphs['star'] = '\u2605'
        glyphs['fail'] = '\u2717'
        glyphs['succ'] = '\u2713'
        glyphs['git'] = '\u237F'
        glyphs['time'] = '\U0000231A'


def init(verbose, color, encoding):
    __set_logger(verbose)
    __set_encoding(encoding)
    pass


def cl(s, color='reset', **args):
    return click.style(s, fg=color, **args)


def utf(k):
    global glyphs
    assert(k in glyphs.keys())
    return glyphs[k]


def print_header(s):
    hdr_char = utf('hdr')
    str_len = globals.LINELENGTH - (len(s) + 2)  # surrounding spaces
    begin = hdr_char * int(str_len / 2)
    end = begin + (hdr_char * (str_len % 2 != 0))

    f = "{} {} {}".format(begin, s.upper(), end)
    click.secho(f, fg="green")
    pass


def print_section(s):
    f = "{} {}".format(utf('sec'), s)
    click.secho(f, fg='yellow', blink=True)


def print_item(s, depth=1):
    bullet = ("   " * depth) + "{} ".format(utf('item'))
    content = "{}".format(s)
    click.secho(bullet, fg="red", nl=False)
    click.secho(content, fg="reset")


def debug(*msg):
    for elt in msg:
        logging.debug(click.style(elt, fg="bright_black"))


def info(*msg):
    for elt in msg:
        logging.info(click.style(elt, fg="blue"))


def warn(*msg):
    for elt in msg:
        logging.warning(click.style(elt, fg="yellow", bold=True))


def err(*msg, abort=0):
    for elt in msg:
        logging.error(click.style(elt, fg="red", bold=True))

    if abort:
        logging.error(click.style("Now going to abort.", fg="red", bold=True))
        sys.exit(abort)

def nimpl(*msg):
    warn("Not implemented! (WIP)")


def nreach(*msg):
    err("Should not be reached!", abort=1)


def banner():
    """ original header to be printed out :
    ____                   ____     __   ______                            __  _            
   / __ \____ __________ _/ / /__  / /  / ____/___  ____ ___  ____  __  __/ /_(_)___  ____ _
  / /_/ / __ `/ ___/ __ `/ / / _ \/ /  / /   / __ \/ __ `__ \/ __ \/ / / / __/ / __ \/ __ `/
 / ____/ /_/ / /  / /_/ / / /  __/ /  / /___/ /_/ / / / / / / /_/ / /_/ / /_/ / / / / /_/ / 
/_/    \__,_/_/   \__,_/_/_/\___/_/   \____/\____/_/ /_/ /_/ .___/\__,_/\__/_/_/ /_/\__, /  
                                                          /_/                      /____/   
                                            (PCVS)                                          
          _    __      ___     __      __  _                _____       _ __     
         | |  / /___ _/ (_)___/ /___ _/ /_(_)___  ____     / ___/__  __(_) /____        
         | | / / __ `/ / / __  / __ `/ __/ / __ \/ __ \    \__ \/ / / / / __/ _ \         
         | |/ / /_/ / / / /_/ / /_/ / /_/ / /_/ / / / /   ___/ / /_/ / / /_/  __/         
         |___/\__,_/_/_/\__,_/\__,_/\__/_/\____/_/ /_/   /____/\__,_/_/\__/\___/ 

  Copyright {} 2017 Commissariat à l'Énergie Atomique et aux Énergies Alternatives (CEA)
  
  This program comes with ABSOLUTELY NO WARRANTY; 
  This is free software, and you are welcome to redistribute it 
  under certain conditions; Please see COPYING for details.
"""

    slice_1 = """\
    ____                   ____     __   ______                            __  _            
   / __ \____ __________ _/ / /__  / /  / ____/___  ____ ___  ____  __  __/ /_(_)___  ____ _
  / /_/ / __ `/ ___/ __ `/ / / _ \/ /  / /   / __ \/ __ `__ \/ __ \/ / / / __/ / __ \/ __ `/
 / ____/ /_/ / /  / /_/ / / /  __/ /  / /___/ /_/ / / / / / / /_/ / /_/ / /_/ / / / / /_/ / 
/_/    \__,_/_/   \__,_/_/_/\___/_/   \____/\____/_/ /_/ /_/ .___/\__,_/\__/_/_/ /_/\__, /  
                                                          /_/                      /____/   """
    slice_2 = """\
                                         {}  (PCVS) {}""".format(utf('star'), utf('star'))
    slice_3 = """\
          _    __      ___     __      __  _                _____       _ __     
         | |  / /___ _/ (_)___/ /___ _/ /_(_)___  ____     / ___/__  __(_) /____"""
    slice_4 = """\
         | | / / __ `/ / / __  / __ `/ __/ / __ \/ __ \    \__ \/ / / / / __/ _ \           
         | |/ / /_/ / / / /_/ / /_/ / /_/ / /_/ / / / /   ___/ / /_/ / / /_/  __/"""
    slice_5 = """\
         |___/\__,_/_/_/\__,_/\__,_/\__/_/\____/_/ /_/   /____/\__,_/_/\__/\___/ """

    slice_6 = """\

  Copyright {} 2017 Commissariat à l'Énergie Atomique et aux Énergies Alternatives (CEA)
  
  This program comes with ABSOLUTELY NO WARRANTY; 
  This is free software, and you are welcome to redistribute it 
  under certain conditions; Please see COPYING for details.
""".format(utf('copy'))
    click.secho(slice_1, fg="green")
    click.secho(slice_2)
    click.secho(slice_3, fg="green")
    click.secho(slice_4, fg="yellow")
    click.secho(slice_5, fg="red")
    click.secho(slice_6)

if __name__ == '__main__':
    pass
