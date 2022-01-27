import os
import json

from flask import Flask
#from werkzeug.utils import import_string

def create_app(test_config=None):
    # Create app
    app = Flask(__name__, instance_relative_config=True)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Configure app
    env = os.environ.get("FLASK_ENV", "Not set")
    if test_config is None and env == "development":
        app.config.from_file("dev_config.json", load=json.load)
    elif test_config is None and env == "production":
        app.config.from_file('prod_config.json', load=json.load)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)
        app.config.from_file('test_config.json', load=json.load)

    # Register functions
    # Register db functions and configure db
    from . import db
    db.init_app(app)
    if env == "development":
        db.setup_db(app)
    elif env == "production":
        db.setup_db(app)

    # Blueprints
    # Register home page blueprint
    from . import home
    app.register_blueprint(home.bp)
    app.add_url_rule("/", endpoint="home")

    # Register admin blueprint
    from . import admin
    app.register_blueprint(admin.bp)
    app.add_url_rule("/admin", endpoint="admin")

    # Register dashboard blueprint
    from . import dashboard
    app.register_blueprint(dashboard.bp)
    app.add_url_rule("/dashboard", endpoint="dashboard")

    return app
