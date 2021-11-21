#!/usr/bin/env python

from setuptools import setup

setup(
    name='asyncbreaker',
    version='0.1.0',
    description='Python implementation of the Circuit Breaker pattern',
    long_description=open('README.md', 'r').read(),
    keywords=['design', 'pattern', 'circuit', 'breaker', 'integration'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries',
    ],
    platforms=[
        'Any',
    ],
    license='BSD',
    author='Mason Data, Daniel Fernandes Martins',
    url='http://github.com/tiwilliam/asyncbreaker',
    package_dir={'': 'src'},
    py_modules=['asyncbreaker'],
    include_package_data=True,
    zip_safe=False,
)
