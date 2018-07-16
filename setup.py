# -*- coding: utf-8 -*-
import os
from setuptools import find_packages, setup
import six

with open(os.path.join(os.path.dirname(__file__), 'requirements.txt')) as f:
    requires = f.readlines()
    if six.PY2:
        requires.append('futures==3.2.0')

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as f:
    README = f.read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))


setup(
    name='rabbit-rpc',
    version='0.0.3',
    packages=find_packages(),
    include_package_data=True,
    description='A simple rpc client/server library',
    long_description=README,
    author='midtin',
    author_email='midtin@gmail.com',
    url='https://github.com/MidTin/rabbit-rpc',
    license='MIT',
    install_requires=requires,
    classifiers=[
        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    entry_points={
        'console_scripts': [
            'rabbit_rpc=rabbit_rpc:main',
        ]
    }
)
