#!/usr/bin/env python

from distutils.core import setup

setup(name='seattle_bike_data',
      version='1.0',
      description='Download and Plot utilities for Seattle bike count data',
      author='Doug Ollerenshaw',
      author_email='d.ollerenshaw@gmail.com',
      url='none,
      packages=['sodapy', 'pandas', 'seaborn', 'matpotlib'],
     )