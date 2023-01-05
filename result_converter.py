import sys
import os
import click
import shutil
import json

from pcvs.testing.test import Test
from pcvs.orchestration.publishers import Publisher

@click.command()
@click.option("-s", "--source", "source", type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help="Source directory/archive to convert")
@click.option("-d", "--dest", "dest", default="./pcvs-result-conversion",
              help="Dest directory where conversion will be stored.")
@click.option("-f", "--force", "force", default=False, is_flag=True,
              help="Override dest directory if if already exists")
def main(source, dest, force):
    
    if "conf.yml" not in os.listdir(source):
        raise click.BadOptionUsage("source", "Source directory is not a valid result directory/archive.")
        
    if os.path.exists(dest) and not force:
        raise click.BadOptionUsage("dest", "Destination directory already exist. Change output directory or use `--force`")
    
    if os.path.exists(dest):
        shutil.rmtree(dest)
        
    os.makedirs(dest)
    man = Publisher(prefix=dest)
    id_incr = 0
    json_filepath = os.path.join(source, "rawdata")
    for f in os.listdir(json_filepath):
        with open(os.path.join(json_filepath, f), 'r') as fh:
            data = json.load(fh)
            assert('tests' in data.keys())
            for test_data in data['tests']:
                job = Test()
                job.from_json(test_data)
                man.save(id_incr, job)
                id_incr += 1
    
    
if __name__ == '__main__':
    main()