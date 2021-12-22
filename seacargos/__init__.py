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
    app.secret_key = "dev"
    env = os.environ.get("FLASK_ENV")
    if test_config is None and env == "development":
        app.config.from_file("dev_config.json", load=json.load)
    elif test_config is None and env == "production":
        app.config.from_file('prod_config.json', load=json.load)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # Register functions
    # Register db functions
    from . import db
    db.init_app(app)

    # Blueprints
    # Register home page blueprint
    from . import home
    app.register_blueprint(home.bp)
    app.add_url_rule('/', endpoint='index')

    return app