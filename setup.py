#!/usr/bin/env python

import setuptools

setuptools.setup(
    name='swaggerspect',
    version='0.0.4',
    description='',
    long_description="""Introspects python classes and functions and generates swagger style documentation objects.""",
    long_description_content_type="text/markdown",
    author='Egil Moeller',
    author_email='em@emrld.no',
    url='https://github.com/emerald-geomodelling/swaggerspect',
    packages=setuptools.find_packages(),
    install_requires=[
        "numpydoc",
    ],
)
