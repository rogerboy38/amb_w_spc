__version__ = '0.0.1'

from setuptools import setup, find_packages
import os

with open('requirements.txt') as f:
    install_requires = f.read().strip().split('\n')

# get version from __version__ variable in amb_w_spc/__init__.py
from amb_w_spc import __version__ as version

setup(
    name='amb_w_spc',
    version=version,
    description='SPC (Statistical Process Control) system for manufacturing quality management',
    author='Your Name',
    author_email='your.email@example.com',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)
