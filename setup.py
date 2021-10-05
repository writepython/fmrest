from __future__ import with_statement
from __future__ import absolute_import
from setuptools import setup
from io import open

with open(u'README.md', u'r', encoding=u'utf-8') as ld:
    long_description = ld.read()

setup(
    name=u'fmrest',
    version=u'1.0.0',
    python_requires=u'>=2.7',
    description=u'python2-fmrest is Python 2 port of the FileMaker Data API wrapper by David Hamann.',
    long_description=long_description,
    long_description_content_type=u'text/markdown',
    url=u'https://github.com/writepython/python2-fmrest',
    packages=[u'fmrest'],
    include_package_data=True,
    install_requires=[u'requests>=2'],
    classifiers=(
        u'Programming Language :: Python',        
        u'Programming Language :: Python :: 2',
        u'Programming Language :: Python :: 2.7',
        u'Programming Language :: Python :: 3.6',
        u'License :: OSI Approved :: MIT License',
        u'Operating System :: OS Independent'
    )
)
