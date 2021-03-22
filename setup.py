import os.path
from setuptools import setup, find_packages

PACKAGE = 'soundserver'


def get_requires(filepath):
    requires = []
    with open(filepath, 'r') as fp:
        for line in fp:
            if line and not line.startswith('#'):
                requires.append(line.strip())
    return requires


about = {}
with open(os.path.join(PACKAGE, '__about__.py'), 'r') as aboutfile:
    exec(aboutfile.read(), about)  # pylint: disable=exec-used

setup(
    name=PACKAGE,
    version=about['__version__'],
    packages=find_packages(include=[PACKAGE, PACKAGE + '.*']),
    python_requires='>3.5',
    install_requires=get_requires('requirements.txt'),
)
