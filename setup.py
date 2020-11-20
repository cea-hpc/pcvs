import setuptools
import subprocess

current_version = subprocess.run("./utils/get_version", stdout=subprocess.PIPE)

with open("README.md", 'r') as f:
    desc = f.read()

with open('requirements.txt') as f:
    requires = f.read().strip().split('\n')


setuptools.setup(
    name="pcvs",
    version=current_version.stdout.decode("utf-8"),
    license="CeCILL-C",
    author="Julien Adam",
    author_email="adamj@paratools.com",
    maintainer="Julien Adam", 
    maintainer_email="adamj@paratools.com",
    keywords="validation hpc test-suite",
    url="https://github.com/cea-hpc/pcvs.git",
    long_description=desc,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    include_package_data=True,
    package_data={
        "pcvs": ["schemes/*.yml", "templates/*.yml", "webview"],
        },

    entry_points='''
        [console_scripts]
        pcvs=pcvs.main:cli
        pcvs_convert=pcvs.converter.yaml_converter:main
    ''',

    classifiers=[
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',

    ],
    install_requires=requires,
    python_requires='>=3.5'
)
