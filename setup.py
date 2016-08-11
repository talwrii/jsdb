import os

from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='jsdb',
    version='0.1',
    author='Tal Wrii',
    author_email='talwrii@gmail.com',
    keywords='database objectstore object-store json persitence',
    url='https://github.com/talwrii/jsdb',
    description='A moderately efficient, pure-python, single-user, JSON, persistent, object-graph database',
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: BSD License"
    ],
    packages=['jsdb']
)
