from setuptools import setup, find_packages
import subprocess

current_version = subprocess.run("./utils/get_version", stdout=subprocess.PIPE)

setup(
    name="pcvs-rt",
    version=current_version.stdout.decode("utf-8"),
    license="CeCILL-C",
    author="Julien Adam",
    author_email="adamj@paratools.com",
    keywords="validation hpc test-suite",
    url="https://github.com/cea-hpc/pcvs.git",

    packages=find_packages(),
    entry_points='''
        [console_scripts]
        pcvs=pcvsrt.scripts.cmd:cli
    ''',

    install_requires=[
        "PyYAML",
        "Click>=7.0",
        "jsonschema"
    ],
)
