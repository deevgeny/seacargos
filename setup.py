# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022  Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from setuptools import find_packages, setup

setup(
    name='seacargos',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'flask',
        'gunicorn'
    ],
)