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

def test_admin_edit_user_response(client, app):
    """Test edit_user() response."""
    with app.app_context():
        # Not logged in user
        response = client.get("/admin/edit-user")
        assert g.user == None
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"
    
        # Logged in user
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        response = login(client, user, pwd)
        assert response.status_code == 200
        response = client.get("/admin/edit-user")
        assert response.status_code == 200

def test_admin_edit_user_form(client, app):
    """Test edit_user() function form."""
    with app.app_context():
        # Login and prepare database
        db = db_conn()[g.db_name]
        db.users.delete_one({"name": "test_1"})
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        login(client, user, pwd)
        response = client.post(
            "/admin/add-user",
            data={"user-name": "test_1", "role": "user",
                "pwd": "abc123", "pwd-repeat": "abc123"},
            follow_redirects=True)
        assert response.status_code == 200

        # All empty fields
        response = client.post(
            "/admin/edit-user",
            data={"user-name": "", "role": "",
                "pwd": "", "pwd-repeat": ""},
            follow_redirects=True)
        assert b"Please select user." in response.data
        
        # All empty fields except user name
        response = client.post(
            "/admin/edit-user",
            data={"user-name": "test_1", "role": "",
                "pwd": "", "pwd-repeat": ""},
            follow_redirects=True)
        assert b"Edit fields have been not filled." in response.data

        # Passwords does not match
        response = client.post(
            "/admin/edit-user",
            data={"user-name": "test_1", "role": "",
                "pwd": "abc123", "pwd-repeat": "123abc"},
            follow_redirects=True)
        assert b"Passwords does not match." in response.data
        
        # Change role
        response = client.post(
            "/admin/edit-user",
            data={"user-name": "test_1", "role": "admin",
                "pwd": "", "pwd-repeat": ""},
            follow_redirects=True)
        assert b"User data successfully updated." in response.data
        cur = db.users.find_one({"name": "test_1"})
        assert cur["role"] == "admin"

        # Change password
        response = client.post(
            "/admin/edit-user",
            data={"user-name": "test_1", "role": "",
                "pwd": "abc123", "pwd-repeat": "abc123"},
            follow_redirects=True)
        assert b"User data successfully updated." in response.data
        cur = db.users.find_one({"name": "test_1"})
        assert check_password_hash(cur["password"], "abc123")
        
        # Update not existing user
        response = client.post(
            "/admin/edit-user",
            data={"user-name": "test_2", "role": "user",
                "pwd": "", "pwd-repeat": ""},
            follow_redirects=True)
        assert b"User data was not updated." in response.data

        # Clear database
        db.users.delete_one({"name": "test_1"})
        del db
