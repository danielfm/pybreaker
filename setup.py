#!/usr/bin/env python
#-*- coding:utf-8 -*-

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, find_packages

setup(
    name = 'circuit-breaker',
    version = '0.1',
    description = 'Pure-Python implementation of the Circuit Breaker pattern',
    keywords = ['design', 'pattern', 'circuit', 'breaker', 'integration'],
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.5',
        'Topic :: Software Development :: Libraries',
    ],
    platforms = [
        'Any',
    ],
    license = 'BSD',
    author = 'Daniel Fernandes Martins',
    author_email = 'daniel@destaquenet.com',
    url = 'http://github.com/danielfm/circuit-breaker-python',
    package_dir = {'':'src'},
    py_modules = ['breaker'],
    include_package_data = True,
    zip_safe = False,
    test_suite = 'tests',

    long_description=
"""
Pure-Python implementation of the Circuit Breaker pattern, described by Michael
T. Nygard in his book 'Release It!'.

For more information on this and other patterns and best practices, buy the
book at http://pragprog.com/titles/mnee/release-it
"""
)
