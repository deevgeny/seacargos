# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

import pytest
from seacargos.db import db_conn, close_db_conn, setup_db
from pymongo import MongoClient
from flask import g
import json
from bson.json_util import dumps
from werkzeug.security import check_password_hash, generate_password_hash

def test_db_conn(app):
    """Test db_conn() function from db.py"""
    with app.app_context():
        assert g.pop("conn", None) == None
        conn = db_conn()
        assert conn is db_conn()
        assert g.conn == conn
    
def test_close_db_conn(app):
    """Test close_db_conn() function."""
    with app.app_context():
        conn = db_conn()
        assert conn == g.conn
        close_db_conn(app)
        assert g.pop("conn", None) == None

def test_setup_db(app):
    """Test setup_db() function."""
    with app.app_context():
        conn = db_conn()
        # Prepare database (delete all users) and check
        conn.test.users.delete_many({})
        assert conn.test.users.count_documents({}) == 0
        # Setup db
        setup_db(app)
        # Count number of records
        assert conn.test.users.count_documents({}) == 2
        # Check user record
        user = conn.test.users.find_one({"name": app.config["USER_NAME"]})
        assert user["name"] == app.config["USER_NAME"]
        assert check_password_hash(
            user["password"], app.config["USER_PASSWORD"]
            )
        assert user["active"] == True
        assert conn.test.users.count_documents(
            {"name": app.config["USER_NAME"],
            "role": "user", "active": True}
            ) == 1
        # Check admin record
        admin = conn.test.users.find_one({"name": app.config["ADMIN_NAME"]})
        assert admin["name"] == app.config["ADMIN_NAME"]
        assert check_password_hash(
            admin["password"], app.config["ADMIN_PASSWORD"]
            )
        assert admin["active"] == True
        assert conn.test.users.count_documents(
            {"name": app.config["ADMIN_NAME"],
            "role": "admin", "active": True}
            ) == 1
        # Re-setup db and check number of users in it
        setup_db(app)
        assert conn.test.users.count_documents({}) == 2
        # Clear db after the tests and check
        #conn.test.users.delete_many({})
        #assert conn.test.users.count_documents({}) == 0

def test_db_users_collection_name_index(app):
    """Test db users collection indexes - name should be unique."""
    with app.app_context():
        # Drop all indexes and check
        conn = db_conn()
        conn.test.users.drop_index("name_index")
        assert len(json.loads(dumps(conn.test.users.list_indexes()))) == 1
        # Run setup_db() function and check that indexes have been added
        setup_db(app)
        cur = conn.test.users.list_indexes()
        indexes = json.loads(dumps(cur))
        assert indexes == [
            {'v': 2, 'key': {'_id': 1}, 'name': '_id_'}, 
            {'v': 2, 'key': {'name': 1}, 'name': 'name_index', 'unique': True}
            ]
