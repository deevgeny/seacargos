from seacargos import create_app
from flask import g


def test_config():
    assert not create_app().testing
    assert create_app({'TESTING': True}).testing
