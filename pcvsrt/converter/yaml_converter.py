import sys
import os
import json
import yaml
import functools
import operator
import pprint
import re
import click

yaml.representer.ignore_aliases = lambda *data: True


def abort(msg):
    print(msg)
    sys.exit(1)


def get_by(data, klist):
    return functools.reduce(operator.getitem, klist, data)


def set_with(data, klist, val):
    for key in klist[:-1]:
        data = data.setdefault(key, {})
    data[klist[-1]] = val


def flatten(dd, prefix=''):
    return { prefix + "." + k if prefix else k : v 
             for kk, vv in dd.items() 
             for k, v in flatten(vv, kk).items() 
             } if isinstance(dd, dict) else {prefix : dd} 


static_fields = dict()


def __process_new_key(k, m):
    replacement = []
    for elt in k.split("."):
            
        if elt.startswith("<") and elt.endswith(">"):
            #tricky cases:
            if '' in elt:
                pass
        
            elt = elt[1:-1]
            if elt in m.groupdict().keys():
                replacement.append(m.group(elt))
            else:
                replacement.append(elt)
        else:
            replacement.append(elt)

    return replacement if replacement else k

def __match_input(key, ref_array):
    for old_k, new_k in ref_array.items():
        r = re.compile(old_k)
        if re.search(r, key) is not None:
            # print("{} == {}".format(old_k, key))    
            # CAUTION: we only parse the first match_obj iteration:
            # we do not consider a token to match multiple times !!!!  
            res = next(r.finditer(key))
            if new_k is not None:
                if isinstance(new_k, list):
                    dest_k = [ __process_new_key(i, res) for i in new_k]
                else:
                    dest_k = [__process_new_key(new_k, res)]
            else:
                dest_k = []
            return (True, dest_k)
        else:
            pass
    return (False, [])        


def process(data, ref_array=None, warn_if_missing=True):
    output = dict()
    if not ref_array:
        ref_array = static_fields['second']
    for k, v in data.items():
        
        # TBW
        (valid, dest_k) = __match_input(k, ref_array)
        
        if valid:
            if len(dest_k) <= 0:
                continue
            for elt_dest_k in dest_k:
                set_with(output, elt_dest_k, v)
        else:
            if warn_if_missing:
                print("missed {} !!".format(k))
            set_with(output, k.split("."), v)

    return output


def process_modifiers(data):
    if "first" in static_fields.keys():
        return process(data, static_fields["first"], warn_if_missing=False)
    else:
        return data

def __replace_token_with_re(tmp, refs):
    final = dict()
    for old, new in tmp.items():
        if old.startswith('__'):
            continue

        replacement = [] 
        for elt in old.split('.'):
            insert = False
            for valid_k in refs.keys():
                if valid_k in elt:
                    insert = True
                    replacement.append(elt.replace(valid_k, refs[valid_k]))
            if not insert:
                replacement.append(re.escape(elt))
        final["\.".join(replacement)] = new
    return final



@click.command("pcvs_convert", help="Tool converting old to new syntax")
@click.option("-k", "--kind", "kind", required=True, type=click.Choice(['compiler', 'runtime', 'environment', 'te'], case_sensitive=False))
@click.option("-s", "--scheme", "scheme", type=click.File(), required=False, default=None)
@click.argument("input_file", type=click.File())
def main(kind, input_file, scheme):

    if not scheme:
        scheme = os.path.join(os.path.dirname(__file__), "convert.json")
    
    data_to_convert = yaml.load(input_file.read(), Loader=yaml.FullLoader)
    
    with open(scheme, 'r') as f:
        tmp = json.load(f)
    
    if '__modifiers' in tmp.keys():
        static_fields['first'] = __replace_token_with_re(tmp['__modifiers'], tmp['__tokens'])
    static_fields['second'] = __replace_token_with_re(tmp, tmp['__tokens'])

    # first, "flattening"
    data_to_convert = flatten(data_to_convert, kind)
    data_to_convert = process_modifiers(data_to_convert)
    # as modifiers may have created nested dictionaries:
    # => "flattening" again, but with no prefix (persistent from first)
    data_to_convert = flatten(data_to_convert, "")
    final_layout = process(data_to_convert)

    prefix, base = os.path.split(input_file.name)
    with open(os.path.join(prefix, "new-"+base), "w") as f:
        yaml.dump(final_layout, f)

    pprint.pprint(final_layout)
    
    



"""
MISSING:
- group
- compiler.package_manager
- runtime.package_manager
- runtime.iterators
- te.package_manager
- herit* become flat
"""
