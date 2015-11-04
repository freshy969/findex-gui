from setuptools import setup, find_packages
import sys
import os


__version__ = '0.0.1'


requires = [
    'python-dateutil',
    'psycopg2',
    'jinja2',
    'sqlalchemy',
    'gevent',
    'bottle-sqlalchemy',
    'bottle',
    'psycogreen',
    'findex-common',
    'click',
    'passlib'
]


def read_file(filename):
    try:
        with open(os.path.join(os.path.dirname(__file__), filename)) as f:
            return f.read()
    except IOError:
        return ''


setup(
    name='findex-gui',
    packages=find_packages(),
    version=__version__,
    description='findex-gui.',
    long_description=read_file('README.md'),
    author='Sander Ferdinand',
    author_email='sa.ferdinand@gmail.com',
    url='https://github.com/skftn/findex-gui/',
    download_url='https://github.com/skftn/findex-gui/tarball/v%s' % __version__,
    install_requires=requires,
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'findex-gui=findex_gui.daemon:cli',
        ],
    },
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
    ],
)
