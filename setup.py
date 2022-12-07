import os
import subprocess
import setuptools

# if installed from Git, put the commit revision
# add -dirty if staged area is not empty
try:
    import sh
    version = sh.git("describe", "--dirty").strip()[1:]
except:
    loc = {}
    with open(os.path.join("pcvs/__init__.py")) as fh:
        exec(fh.read(), None, loc)
    version = loc['__version__']

with open("README.md", 'r') as f:
    desc = f.read()

with open('requirements.txt') as f:
    requires = f.read().strip().split('\n')


setuptools.setup(
    name="pcvs",
    version=version,
    license="CeCILL-C",
    author="Julien Adam",
    author_email="adamj@paratools.com",
    maintainer="Julien Adam",
    maintainer_email="adamj@paratools.com",
    keywords="validation hpc test-suite",
    url="https://pcvs.io/",
    long_description=desc,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    include_package_data=True,
    package_data={
        "pcvs": [
            "schemes/*.yml",
            "templates/*.yml", "templates/*.json",
            "examples/*.yml", "examples/*.json"
            ],
        },

    entry_points='''
        [console_scripts]
        pcvs=pcvs.main:cli
        pcvs_convert=pcvs.converter.yaml_converter:main
    ''',

    project_urls={
        "Source Code": "https://github.com/cea-hpc/pcvs.git/",
        "Documentation": "https://pcvs.readthedocs.io/",
        },
    classifiers=[
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',

    ],
    install_requires=requires,
    python_requires='>=3.5'
)
