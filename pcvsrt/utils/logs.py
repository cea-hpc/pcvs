import sys
import os
import logging
import textwrap

PREFIXPATH = "/../"
BASEPATH = os.path.abspath(os.path.join(os.path.dirname(__file__) + PREFIXPATH))
FORMAT = "%(levelname)s: %(message)s"

LINELENGTH=80
colors = {}
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

    pass


def __set_color(c):
    global colors
    if c:
        colors = {
            'r': 31,
            'g': 32,
            'y': 33,
            'b': 34,
            'grey': 90,
            'reset': 0
        }

def __set_encoding(e):
    global glyphs
    if e and 'utf-' in sys.getdefaultencoding():
        glyphs['copy'] = '\u00A9'
        glyphs['item'] = '\u27E2'
        glyphs['sec'] = '\u2756'
        glyphs['hdr'] = '\u2015'
        glyphs['star'] = '\u2605'
        glyphs['fail'] = '\u2717'
        glyphs['succ'] = '\u2713'
        glyphs['git'] = '\u237F'
        glyphs['time'] = '\U0000231A'


def init(verbose, color, encoding):
    __set_logger(verbose)
    __set_color(color)
    __set_encoding(encoding)
    pass


def cl(c, b=0):
    global colors
    if colors:
        return "\033[" + str(b) + ";" + str(colors[c]) + "m"
    else:
        return ""

def utf(k):
    global glyphs
    assert(k in glyphs.keys())
    return glyphs[k]

def print_header(s):
    hdr_char = utf('hdr')
    str_len = LINELENGTH - (len(s) + 2)  # surrounding spaces
    begin = hdr_char * int(str_len / 2)
    end = begin + (hdr_char * (str_len % 2 != 0))
    print("\n{}{} {} {}{}".format(cl('g'), begin, s.upper(), end, cl('reset')))
    pass


def print_section(s):
    print("{}{} {}{}".format(cl('y'), utf('sec'),
                               textwrap.fill(s.title(), width=LINELENGTH),
                               cl('reset')))


def print_item(s, depth=1):
    print(("   " * depth) + "{}{}{} {}".format(cl('r'),
                                               utf('item'), cl('reset'),
                                               textwrap.fill(s.capitalize(),
                                                             width=LINELENGTH)))
    pass


def debug(*msg):
    for elt in msg:
        logging.debug(cl('grey')+elt+cl('reset'))


def info(*msg):
    for elt in msg:
        logging.info(cl('b')+elt+cl('reset'))


def warn(*msg):
    for elt in msg:
        logging.warning(cl('y', 1)+elt+cl('reset'))


def err(*msg, abort=0):
    for elt in msg:
        logging.error(cl('r', 1)+elt+cl('reset'))

    if abort:
        logging.error(cl('r', 1)+"Now going to abort."+cl('reset'))
        sys.exit(42)

def set_tee():
    pass




def banner():
    print(r"""{}
    ____                   ____     __   ______                            __  _            
   / __ \____ __________ _/ / /__  / /  / ____/___  ____ ___  ____  __  __/ /_(_)___  ____ _
  / /_/ / __ `/ ___/ __ `/ / / _ \/ /  / /   / __ \/ __ `__ \/ __ \/ / / / __/ / __ \/ __ `/
 / ____/ /_/ / /  / /_/ / / /  __/ /  / /___/ /_/ / / / / / / /_/ / /_/ / /_/ / / / / /_/ / 
/_/    \__,_/_/   \__,_/_/_/\___/_/   \____/\____/_/ /_/ /_/ .___/\__,_/\__/_/_/ /_/\__, /  
                                                          /_/                      /____/   {}
                                         {} (PCVS) {}{}                                     
          _    __      ___     __      __  _                _____       _ __     
         | |  / /___ _/ (_)___/ /___ _/ /_(_)___  ____     / ___/__  __(_) /____            {}
         | | / / __ `/ / / __  / __ `/ __/ / __ \/ __ \    \__ \/ / / / / __/ _ \           
         | |/ / /_/ / / / /_/ / /_/ / /_/ / /_/ / / / /   ___/ / /_/ / / /_/  __/         {}  
         |___/\__,_/_/_/\__,_/\__,_/\__/_/\____/_/ /_/   /____/\__,_/_/\__/\___/ 
{}

  Copyright {} 2017 Commissariat à l'Énergie Atomique et aux Énergies Alternatives (CEA)
  
  This program comes with ABSOLUTELY NO WARRANTY; 
  This is free software, and you are welcome to redistribute it 
  under certain conditions; Please see COPYING for details.
""".format(cl('g'), cl('reset'), utf('star'), utf('star'), cl('g'), cl('y'), cl('r'), cl('reset'), utf('copy')))


if __name__ == '__main__':
    pass
