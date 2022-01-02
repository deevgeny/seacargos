from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure
from bson.json_util import dumps
import json
from werkzeug.security import check_password_hash, generate_password_hash

import click
from flask import current_app, g
from flask.cli import with_appcontext

def db_conn():
    """Open MongoDB connection, add to g and return."""
    if 'conn' not in g:
        g.conn = MongoClient(current_app.config['DB_FRONTEND_URI'])
        g.db = current_app.config["DB_NAME"]
    return g.conn

def close_db_conn(exception):
    """Pop MongoDB connection object from g and close."""
    conn = g.pop('conn', None)

    if conn is not None:
        g.pop('db', None)
        conn.close()

# Register close_conn() function with application
def init_app(app):
    """Add close_db_conn() to teardown appcontext."""
    app.teardown_appcontext(close_db_conn)

def setup_db(app):
    """Add 2 first users to database."""
    # Connect to database
    conn = MongoClient(app.config['DB_FRONTEND_URI'])
    db = conn[app.config["DB_NAME"]]

    # Add admin user to database
    cur = db.users.find_one({"name": app.config["ADMIN_NAME"]})
    if cur is None:
        pwd = generate_password_hash(app.config['ADMIN_PASSWORD'])
        db.users.insert_one(
            {'name': app.config['ADMIN_NAME'],
            'password': pwd,
            'role': 'admin'}
        )

    # Add simple user to database
    cur = db.users.find_one({"name": app.config["USER_NAME"]})
    if cur is None:
        pwd = generate_password_hash(app.config['USER_PASSWORD'])
        db.users.insert_one(
            {'name': app.config['USER_NAME'],
            'password': pwd,
            'role': 'user'}
        )
    
    # Add username unique index to database users collection
    cur = db.users.list_indexes()
    idxs = json.loads(dumps(cur))
    if len(idxs) == 1:
        db.users.create_index(
            [("name", ASCENDING)],
            unique=True,
            name="name_index"
            )

    conn.close()