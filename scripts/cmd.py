#!/usr/bin/env python3

import click
import os

command_dir = os.path.join(os.path.dirname(__file__), 'commands')

@click.group()
@click.option("-t", "--test", "t", default=1)
def cli(t):
    pass

@cli.command(name="run")
@click.option("-v", default=2)
def parse_run_cli(v):
    print("Hello with v = %d" % v)

if __name__ == '__main__':
    cli()
    pass