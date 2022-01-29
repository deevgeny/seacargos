# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022  Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from seacargos import create_app
from flask import g
import os


def test_create_app_factory_config():
    # Test "test" configuration
    assert not create_app().testing
    assert create_app({'TESTING': True}).testing

    # Test development configuration
    os.environ["FLASK_ENV"] = "development"
    app = create_app()
    with app.app_context():
        assert app.config["DB_NAME"] == "development"

    # Test production configuration
    os.environ["FLASK_ENV"] = "production"
    app = create_app()
    with app.app_context():
        assert app.config["DB_NAME"] == "production"
