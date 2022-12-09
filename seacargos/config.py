import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask

import admin
import dashboard
import db
import home

logging.basicConfig(
    level=logging.INFO,
    handlers=[RotatingFileHandler(
        'logs/one.log', maxBytes=5000000, backupCount=5)],
    format=('%(asctime)s - %(levelname)s - %(name)s - '
            '%(filename)s in %(funcName)s:%(lineno)s - %(message)s')
)


def create_app(test_config=None):
    # Create app
    app = Flask(__name__, instance_relative_config=True)

    # Configure app
    app.config.from_prefixed_env()
    env = os.environ.get("FLASK_ENV", "Not set")

    # Register db functions and configure db
    db.init_app(app)
    if env == "development" or env == "production":
        db.setup_db(app)

    # Register blueprints
    app.register_blueprint(home.bp)
    app.add_url_rule("/", endpoint="home")

    app.register_blueprint(admin.bp)
    app.add_url_rule("/admin/", endpoint="admin")

    app.register_blueprint(dashboard.bp)
    app.add_url_rule("/dashboard/", endpoint="dashboard")

    return app
