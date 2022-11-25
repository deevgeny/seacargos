import json
import logging
from typing import Optional

from bson.json_util import dumps
from flask import Flask, current_app, g
from pymongo import ASCENDING, MongoClient
from pymongo.errors import ConnectionFailure
from werkzeug.security import generate_password_hash

logger = logging.getLogger("DATABASE")


def db_conn() -> Optional[MongoClient]:
    """Open MongoDB connection.

    Update Flask g object:
    - g.conn = MongoClient.
    - g.db_name = database name to use.
    """
    if 'conn' not in g:
        try:
            g.conn = MongoClient(current_app.config['DB_FRONTEND_URI'])
            g.db_name = current_app.config["DB_NAME"]
        except ConnectionFailure:
            logger.error("Database connection failure.")
            return
        except BaseException as e:
            logger.error(f"Unexpected error: {e.args}")
            return
    return g.conn


def close_db_conn(exception: BaseException) -> None:
    """Pop MongoDB connection object from Flask g object and close."""
    conn = g.pop('conn', None)

    if conn is not None:
        g.pop('db', None)
        conn.close()


def init_app(app: Flask) -> None:
    """Add close_db_conn() to teardown appcontext."""
    app.teardown_appcontext(close_db_conn)


def setup_db(app: Flask) -> None:
    """Setup database.

    Add 2 first users to database with credentials setup in .env file.
    """
    # Connect to database
    try:
        conn = MongoClient(app.config['DB_FRONTEND_URI'])
        db = conn[app.config["DB_NAME"]]
    except ConnectionFailure:
        logger.error("Database connection failure")
    except BaseException as e:
        logger.error(f"Unexpected error: {e.args}")

    # Add admin user to database
    cur = db.users.find_one({"name": app.config["ADMIN_NAME"]})
    if not cur:
        pwd = generate_password_hash(app.config['ADMIN_PASSWORD'])
        db.users.insert_one(
            {'name': app.config['ADMIN_NAME'],
             'password': pwd,
             'role': 'admin',
             'active': True}
        )

    # Add simple user to database
    cur = db.users.find_one({"name": app.config["USER_NAME"]})
    if not cur:
        pwd = generate_password_hash(app.config['USER_PASSWORD'])
        db.users.insert_one(
            {'name': app.config['USER_NAME'],
             'password': pwd,
             'role': 'user',
             'active': True}
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
