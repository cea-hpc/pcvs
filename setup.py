from setuptools import setup, find_packages
import subprocess

current_version = subprocess.run("./utils/get_version", stdout=subprocess.PIPE) 

setup(
    name="PCVS-rt",
    version=current_version.stdout.decode("utf-8"),
    license="CeCILL-C",
    scripts=["scripts/cmd"],
    packages=find_packages(),

    author="Julien Adam",
    author_email="adamj@paratools.com",
    keywords="validation hpc test-suite",
    url="",

    
    install_requires=[
        "PyYAML",
        "jsonschema"
    ],
)
