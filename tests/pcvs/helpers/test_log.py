import os
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from pcvs.helpers import log as tested
from pcvs.helpers.exceptions import CommonException


def test_manager_init():
    assert(tested.IOManager() is not None)
    assert(tested.IOManager(verbose=0).verbose == 0)
    assert(tested.IOManager(tty=False).tty is False)
    with CliRunner().isolated_filesystem():
        assert(tested.IOManager(logfile="./test.log").log_filename == 
            os.path.join(os.getcwd(), "test.log"))

@pytest.mark.parametrize('verbosity', [
    (0, "normal", ["normal"]),
    (1, "info", ["normal", "info"]),
    (2, "debug", ["normal", "info", "debug"])
])
def test_verbosity(verbosity):
    assert(len(tested.IOManager.verb_levels) == 3)
    assert((0, "normal") in tested.IOManager.verb_levels)
    assert((1, "info") in tested.IOManager.verb_levels)
    assert((2, "debug") in tested.IOManager.verb_levels)
    
    obj = tested.IOManager(verbose=verbosity[0])
    assert(obj.verbose == verbosity[0])
    assert(obj.get_verbosity_str() == verbosity[1])
    for level in [name for num, name in tested.IOManager.verb_levels]:
        if level in verbosity[2]:
            assert(obj.has_verb_level(level))
        else:
            assert(not obj.has_verb_level(level))

def test_unicode():
    assert('unicode' in tested.IOManager.special_chars)
    assert('ascii' in tested.IOManager.special_chars)
    assert(len(tested.IOManager.special_chars['unicode']) == len(tested.IOManager.special_chars['ascii']))

    obj = tested.IOManager(enable_unicode=True)
    assert(obj.utf("succ") == tested.IOManager.special_chars['unicode']['succ'])
    assert(obj.utf("fail") == tested.IOManager.special_chars['unicode']['fail'])
    assert(obj.utf("hdr") == tested.IOManager.special_chars['unicode']['hdr'])

    obj.enable_unicode(False)
    assert(obj.utf("succ") == tested.IOManager.special_chars['ascii']['succ'])
    assert(obj.utf("fail") == tested.IOManager.special_chars['ascii']['fail'])
    assert(obj.utf("hdr") == tested.IOManager.special_chars['ascii']['hdr'])

def test_print_tty(capsys):
    obj = tested.IOManager(tty=True, enable_unicode=False)
    obj_default = tested.IOManager()
    assert(obj.tty == obj_default.tty)

    obj.print('test')
    assert('test\n' == capsys.readouterr().out)
    assert("== TEST ==" in obj.print_header('test', out=False))
    assert("# test" in obj.print_section("test", out=False))
    assert(" *" in obj.print_item("test", out=False))
    assert("     *" in obj.print_item("test", out=False, depth=4))

def test_print_file():
    with CliRunner().isolated_filesystem():
        obj = tested.IOManager(logfile="temp.log", enable_unicode=False)
        obj2 = tested.IOManager()
        assert(obj.log_filename == os.path.join(os.getcwd(), "temp.log"))
        assert(obj2.log_filename is None)
        obj.print("test")
        obj.print_header("test")
        obj.print_section("test")
        obj.print_item("test")
        obj.print_item("test", depth=4)
        del obj
        
        presumed_file = os.path.join(os.getcwd(), "temp.log")
        assert(os.path.isfile(presumed_file))
        
        with open(presumed_file, 'r') as fh:
            stream = fh.read()
            assert('test' in stream)
            assert("== TEST ==" in stream)
            assert("# test" in stream)
            assert(" *" in stream)
            assert("     *" in stream)
        
        with pytest.raises(CommonException.AlreadyExistError):
                obj2 = tested.IOManager(logfile="temp.log")


def test_print_logcall(capsys):
    with CliRunner().isolated_filesystem():
        obj_normal = tested.IOManager(verbose=0, tty=False, logfile="normal.log")
        obj_info = tested.IOManager(verbose=1, tty=False, logfile="info.log")
        obj_debug = tested.IOManager(verbose=2, tty=False, logfile="debug.log")
        
        for man in [obj_normal, obj_info, obj_debug]: 
            man.err('test')
            man.warn('test')
            man.info('test')
            man.debug("test")
            print(os.path.isfile('debug.log'))
        man = None

        # close log_files
        del obj_normal
        del obj_info
        del obj_debug
        
        with open("normal.log", 'r') as fh:
            stream = fh.read()
            assert('ERROR: ' in stream)
            assert('WARN : ' in stream)
            assert('INFO : ' not in stream)
            assert('DEBUG: ' not in stream)
        
        with open("info.log", 'r') as fh:
            stream = fh.read()
            assert('ERROR:' in stream)
            assert('WARN :' in stream)
            assert('INFO :' in stream)
            assert('DEBUG:' not in stream)

        with open("debug.log", 'r') as fh:
            stream = fh.read()
            assert('ERROR:' in stream)
            assert('WARN :' in stream)
            assert('INFO :' in stream)
            assert('DEBUG:' in stream)
    
def test_banners(capsys):
    obj = tested.IOManager(length=100)
    obj.print_banner()

    banner = capsys.readouterr().out
    assert(banner != obj.print_short_banner(string=True))
    assert("Commissariat à l'Énergie Atomique et aux Énergies Alternatives (CEA)" in banner)
    
    obj = tested.IOManager(length=60)
    obj.print_banner()
    banner = capsys.readouterr().out
    assert("Parallel Computing -- Validation System" in banner)
    assert("-- CEA" in banner)

    obj = tested.IOManager(length=20)
    obj.print_banner()
    banner = capsys.readouterr().out
    assert("-- PCVS --" in banner)
    assert("CEA" in banner)
    

    
    
