# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from flask import g, session, get_flashed_messages
from pymongo.mongo_client import MongoClient
from seacargos.db import db_conn

# Helper functions to run tests
def login(client, user, pwd, follow=True):
    """Simple login function."""
    return client.post(
        "/", data={"username": user, "password": pwd},
        follow_redirects=follow)

def logout(client, follow=True):
    """Simple logout function."""
    return client.get("/logout", follow_redirects=follow)

def test_admin_unblock_user_response(client, app):
    """Test unblock_user() response."""
    with app.app_context():
        # Prepare test database (set all users active)
        db = db_conn()[g.db_name]
        db.users.update_many({}, {"$set": {"active": True}})

        # Not logged in user
        response = client.get("/admin/block-user")
        assert g.user == None
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"
    
        # Logged in user
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        response = login(client, user, pwd)
        assert g.user != None
        assert response.status_code == 200
        response = client.get("/admin/block-user")
        assert response.status_code == 200
        logout(client)
        assert g.user == None

        # Wrong user role
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        response = login(client, user, pwd)
        assert g.user != None
        assert response.status_code == 200
        response = client.get("/admin/block-user")
        assert response.status_code == 403
        assert b'You are not authorized to view this page.' in response.data
        logout(client)
        assert g.user == None

def test_admin_unblock_user_form(client, app):
    """Test unblock_user() form."""
    with app.app_context():
        # Error "User data was not updated" not covered
        # Login and prepare database
        db = db_conn()[g.db_name]
        db.users.update_many({"name": "test"}, {"$set": {"active": False}})
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        login(client, user, pwd)

        # Block one user
        response = client.post(
            "/admin/unblock-user",
            data={"user-name": "test"},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b"User successfully unblocked." in response.data
        assert db.users.count_documents({"active": False}) == 0

        # Block empty user
        response = client.post(
            "/admin/unblock-user",
            data={"user-name": ""},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b"Please select user." in response.data
        assert db.users.count_documents({"active": False}) == 0

        # Restore database data to initial state
        db.users.update_many({}, {"$set": {"active": True}})
        del db