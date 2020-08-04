import json
import os
import pprint
import re
import sys

import click
import pkg_resources
import yaml

from pcvsrt import logs

desc_dict = dict()


def separate_key_and_value(s: str, c: str) -> tuple:
    """ helper to split the key and value from a string"""
    array = s.split(c)
    if len(array) > 1:
        return (array[0], "".join(array[1:]))
    else:
        return (s, None)


def set_with(data, klist, val, append=False):
    """Add a value to a n-depth dict where the depth is declared as
    a list of intermediate keys. the 'append' flag indicates if the given
    'value' should be appended or replace the original content
    """
    # Just in case intermediate keys do not exist
    for key in klist[:-1]:
        data = data.setdefault(key, {})

    # if the value should be appended
    if append:
        # if the key doe not exist, create the list
        if klist[-1] not in data:
            data[klist[-1]] = list()
        # if it exists and is not a list ==> complain!
        elif not isinstance(data[klist[-1]], list):
            raise TypeError("fail")
        # append the value
        data[klist[-1]].append(val)
    else:
        # replace the value
        data[klist[-1]] = val


def flatten(dd, prefix='') -> dict:
    """ make the n-depth dict 'dd' a "flat" version, where the successive keys
    are chained in a tuple. for instance:
    {'a': {'b': {'c': value}}} --> {('a', 'b', 'c'): value}
    """
    return {prefix + "." + k if prefix else k: v
            for kk, vv in dd.items()
            for k, v in flatten(vv, kk).items()
            } if isinstance(dd, dict) else {prefix: dd}


def compute_new_key(k, m) -> str:
    """replace in 'k' any pattern found in 'm'.
    'k' is a string with placeholders, while 'm' is a match result with groups
    named after placeholders.
    This function will also expand the placeholder if 'call:' token is used to
    execute python code on the fly (complex transformation)
    """
    replacement = ""
    # basic replace the whole string with any placeholder
    for elt in m.groupdict().keys():
        k = k.replace("<"+elt+">", m.group(elt))

    # if this key is a special python expression to process:
    if k.startswith('call:'):
        env = {'k': k, 'm': m}
        # the 'k' & 'm' vars are exposed to evaluated code
        code = compile(k.split("call:")[1], 'user-defined', 'exec')
        eval(code, env)
        # the 'k' is retrieved and used as a whole
        replacement = env['k']
    else:
        replacement = k
    return replacement


def check_if_key_matches(key, ref_array) -> tuple:
    """list all matches for the current key in the new YAML description."""
    # for each key to be replaced.
    # WARNING: no order!
    for old_k, new_k in ref_array.items():
        # compile the regex (useful ?)
        r = re.compile(old_k)
        if re.search(r, key) is not None:  # if the key exist
            # CAUTION: we only parse the first match_obj iteration:
            # we do not consider a token to match multiple times in
            # the source key!
            res = next(r.finditer(key))
            # if there is a associated key in the new tree
            if new_k is not None:
                if isinstance(new_k, list):
                    dest_k = [compute_new_key(i, res) for i in new_k]
                else:
                    dest_k = [compute_new_key(new_k, res)]
            else:
                dest_k = []
            return (True, dest_k)
        else:  # the key does not exist
            pass
    return (False, [])


def process(data, ref_array=None, warn_if_missing=True) -> dict:
    """Process YAML dict 'data' and return a transformed dict"""
    output = dict()

    # desc_dict['second'] is set to contain all keys
    # by opposition to desc_dict['first'] containing modifiers
    if not ref_array:
        ref_array = desc_dict['second']

    # browse original data
    for k, v in data.items():
        # if the node changed and should be moved, the tuple contains:
        # - valid = node changed = key has been found in the desc.
        # - dest_k = an array where each elt can be:
        #    * the new key value
        #    * the new key alongside with the transformed value as well
        # in the latter case, a split is required to identify key & value
        # an array is returned as a single node can produe multiple new nodes
        (valid, dest_k) = check_if_key_matches(k, ref_array)

        if valid:
            logs.info("Processing {}".format(k))
            # An empty array means the key does not exist in the new tree.
            # => discard
            if len(dest_k) <= 0:
                continue

            # Process each of the new keys
            for elt_dest_k in dest_k:
                (final_k, final_v, token) = (elt_dest_k, None, '')
                # if a split is required
                for token in ['+', '=']:
                    (final_k, final_v) = separate_key_and_value(elt_dest_k,
                                                                token)
                    # the split() succeeded ? stop
                    if final_v:
                        break

                # special case to handle the "+" operator to append a value
                should_append = (token == '+')
                # if none of the split() succeeded, just keep the old value
                final_v = v if not final_v else final_v
                # set the new key with the new value
                set_with(output, final_k.split('.'), final_v, should_append)
        else:
            # warn when an old_key hasn't be declared in spec.
            logs.info("DISCARDING {}".format(k))
            if warn_if_missing:
                logs.warn("Key {} undeclared in spec.".format(k))
            # but still, keep it in the final output
            set_with(output, k.split("."), v)
    return output


def process_modifiers(data):
    """applies rules in-place for the data dict.
    Rules are present in the desc_dict['first'] sub-dict."""
    if "first" in desc_dict.keys():
        # do not warn for missing keys in that case (incomplete)
        return process(data, desc_dict["first"], warn_if_missing=False)
    else:
        return data


def replace_placeholder(tmp, refs) -> dict:
    """
    The given TMP should be a dict, where keys contain placeholders, wrapped
    with "<>". Each placeholder will be replaced (i.e. key will be changed) by
    the associated value in refs."""

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
        final[r"\.".join(replacement)] = new
    return final


def print_version(ctx, param, value) -> None:
    """print converter version number, tied to PCVS-RT version number """
    if not value or ctx.resilient_parsing:
        return
    version = pkg_resources.require("pcvs-rt")[0].version
    click.echo('YAML Converter (pcvs-rt Suite) -- version {}'.format(version))
    ctx.exit()


@click.command("pcvs_convert", short_help="YAML to YAML converter")
@click.option("-k", "--kind", "kind",
              type=click.Choice(['compiler', 'runtime', 'environment', 'te'],
                                case_sensitive=False),
              required=True, help="Select a kind to apply for the file")
@click.option("-t", "--template", "template",
              type=click.Path(exists=True, dir_okay=False, readable=True),
              required=False, default=None,
              help="Optional template file (=group) to resolve aliases")
@click.option("-s", "--scheme", "scheme", required=False, default=None,
              type=click.Path(exists=True, dir_okay=False, readable=True),
              help="Override default spec by custom one")
@click.option("-v", "--verbose", count=True,
              help="Enable up to 3-level log messages")
@click.option("-V", "--version", expose_value=False, callback=print_version,
              is_eager=True, help="Print version", is_flag=True)
@click.option("-c", "--color/--no-color", "color",
              default=True, is_flag=True, show_envvar=True,
              help="Use colors to beautify the output")
@click.option("-g", "--glyph/--no-glyph", "encoding",
              default=True, is_flag=True, show_envvar=True,
              help="enable/disable Unicode glyphs")
@click.option("-o", "--output", "out", default=None,
              type=click.Path(exists=False, dir_okay=False),
              help="Filepath where to put the converted YAML")
@click.option("--stdout", "stdout", is_flag=True, default=False,
              help="Print the stdout nothing but the converted data")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False,
                                              readable=True, allow_dash=True))
@click.option("-F", "--fancy", "enrich_exp", default=False, is_flag=True,
              help="Visually enrich your PCVS experience :)")
@click.pass_context
def main(ctx, color, encoding, verbose, kind, input_file, out, enrich_exp, scheme, template, stdout) -> None:
    """
    Process the conversion from one YAML format to another.
    Conversion specifications are described by the SCHEME file.
    """
    # Click specific-related
    ctx.color = color
    kind = kind.lower()
    logs.init(verbose, encoding, enrich_exp)
    logs.enrich_print(
        "Welcome to this PCVS-oriented YAML to YAML converter."
        "The purpose of this script is to convert files from the old deprecated"
        " syntax to the new one in a minimal effort. Please note that because"
        " of the large flexibility allowed by the syntax, the conversion may"
        " fail and a human proofreading is required to ensure correctness",
        skippable=True
    )
    logs.print_header("YAML Conversion")
    

    if template is None and kind == "te":
        logs.warn("If the TE file contains YAML aliases, the conversion may",
                  "fail. Use the '--template' option to provide the YAML file",
                  "containing these aliases")
    # load the input file
    f = sys.stdin if input_file == '-' else open(input_file, 'r')
    try:
        logs.print_item("Load data file: {}".format(f.name))
        stream = f.read()
        if template:
            logs.print_item("Load template file: {}".format(template))
            stream = open(template, 'r').read() + stream
        data_to_convert = yaml.load(stream, Loader=yaml.FullLoader)
    except yaml.composer.ComposerError as e:
        logs.err("Issue when parsing YAML: ", "{}".format(e), abort=1)

    # load the scheme
    if not scheme:
        scheme = open(os.path.join(os.path.dirname(__file__), "convert.json"))
    logs.print_item("Load scheme file: {}".format(scheme.name))
    tmp = json.load(scheme)

    # if modifiers are declared, replace token with regexes
    if '__modifiers' in tmp.keys():
        desc_dict['first'] = replace_placeholder(tmp['__modifiers'],
                                                 tmp['__tokens'])
    desc_dict['second'] = replace_placeholder(tmp,
                                              tmp['__tokens'])

    logs.info("Conversion list {old_key -> new_key):",
              "{}".format(pprint.pformat(desc_dict)))

    # first, "flattening" the original array: {(1, 2, 3): "val"}
    data_to_convert = flatten(data_to_convert, kind)

    # then, process modifiers, altering original data before processing
    logs.print_item("Process alterations to the original data")
    data_to_convert = process_modifiers(data_to_convert)
    # as modifiers may have created nested dictionaries:
    # => "flattening" again, but with no prefix (persistent from first)
    data_to_convert = flatten(data_to_convert, "")

    # Finally, convert the original data to the final yaml dict
    logs.print_item("Process the data")
    final_data = process(data_to_convert)
    logs.info("Final layout:", "{}".format(pprint.pformat(final_data)))

    if stdout:
        f = sys.stdout
    else:
        if out is None:
            prefix, base = os.path.split(
                "./file.yml" if input_file == "-" else input_file)
            out = os.path.join(prefix, "convert-" + base)
        f = open(out, "w")

    logs.print_section("Converted data written into {}".format(f.name))
    yaml.dump(final_data, f)

    f.close()

"""
MISSING:
- compiler.package_manager
- runtime.package_manager
- te.package_manager
"""