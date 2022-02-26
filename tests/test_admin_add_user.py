# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

import os
from flask import g, session, get_flashed_messages
from pymongo.mongo_client import MongoClient
from seacargos.db import db_conn
from werkzeug.security import check_password_hash, generate_password_hash

# Helper functions to run tests
def login(client, user, pwd, follow=True):
    """Simple login function."""
    return client.post(
        "/", data={"username": user, "password": pwd},
        follow_redirects=follow)

def test_admin_add_user_response(client, app):
    """Test add_user() response."""
    with app.app_context():
        # Not logged in user
        response = client.get("/admin/add-user")
        assert g.user == None
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"
    
        # Logged in user
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        response = login(client, user, pwd)
        assert response.status_code == 200
        response = client.get("/admin/add-user")
        assert response.status_code == 200

def test_admin_add_user_form(client, app):
    """Test add_user() form."""
    with app.app_context():
        # "Database write error" not covered
        # Login and prepare database
        db = db_conn()[g.db_name]
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        login(client, user, pwd)
        db.users.delete_one({"name": "test_1"})
        db.users.delete_one({"name": "test_2"})
        
        # Add new user with 'user' role and 'test_1' name
        response = client.post(
            "/admin/add-user",
            data={"user-name": "test_1", "role": "user",
                "pwd": "abc123", "pwd-repeat": "abc123"},
            follow_redirects=True)
        assert b"New user successfully added to database." in response.data
        rec = db.users.find_one({"name": "test_1"})
        assert rec["role"] == "user"
        assert check_password_hash(rec["password"], "abc123")
        
        # Add new user with 'admin' role and 'test_2' name
        response = client.post(
            "/admin/add-user",
            data={"user-name": "test_2", "role": "admin",
                "pwd": "123abc", "pwd-repeat": "123abc"},
            follow_redirects=True)
        assert b"New user successfully added to database." in response.data
        rec = db.users.find_one({"name": "test_2"})
        assert rec["role"] == "admin"
        assert check_password_hash(rec["password"], "123abc")

        # Add duplicate user with 'user' role and 'test_1' name
        response = client.post(
            "/admin/add-user",
            data={"user-name": "test_1", "role": "user",
                "pwd": "abc123", "pwd-repeat": "abc123"},
            follow_redirects=True)
        assert b"User name test_1 already exists." in response.data
        
        # Add user with 'user' role, 'test_3' name and mismatched passwords
        response = client.post(
            "/admin/add-user",
            data={"user-name": "test_3", "role": "user",
                "pwd": "abc123", "pwd-repeat": "abc1234"},
            follow_redirects=True)
        assert b"Passwords does not match." in response.data
        assert db.users.count_documents({"name": "test_3"}) == 0
        
        # Add user with no role and 'test_3' name
        response = client.post(
            "/admin/add-user",
            data={"user-name": "test_3", "role": "",
                "pwd": "abc123", "pwd-repeat": "abc123"},
            follow_redirects=True)
        assert b"Please select role." in response.data
        assert db.users.count_documents({"name": "test_3"}) == 0

        # Clean database
        db.users.delete_one({"name": "test_1"})
        db.users.delete_one({"name": "test_2"})
        del db

