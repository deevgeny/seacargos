# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from flask import g, session

from seacargos.db import db_conn
from werkzeug.security import generate_password_hash

# Helper functions to run tests
def login(client, user, pwd, follow=True):
    """Simple login function."""
    return client.post(
        "/", data={"username": user, "password": pwd},
        follow_redirects=follow)

def logout(client, follow=True):
    """Simple logout function."""
    return client.get("/logout", follow_redirects=follow)

# View tests
def test_home_simple_login(client, app):
    """Test home page for different logins."""
    with app.app_context():
        # Prepare test database (set all users active)
        db = db_conn()[g.db_name]
        db.users.delete_one({"name": "fake"})
        db.users.update_many({}, {"$set": {"active": True}})

        # Unauthenticated user
        response = client.get("/")
        assert response.status_code == 200
        assert g.user == None

        # Log in user with role=user
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        response = login(client, user, pwd)
        assert response.status_code == 200
        assert g.user != None
        logout(client)
        assert g.user == None
        
        # Log in user with role=admin
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        response = login(client, user, pwd)
        assert response.status_code == 200
        assert g.user != None
        logout(client)
        assert g.user == None

        # Log in user with role=fake
        db = db_conn()[g.db_name]
        pwd_hash = generate_password_hash("fake")
        db.users.insert_one(
            {"name": "fake", "password": pwd_hash,
            "role": "fake", "active": True}
            )
        response = login(client, "fake", "fake")
        assert response.status_code == 200
        assert g.user == None
        db.users.delete_one({"name": "fake"})

        # Locked user ("active": False)
        db.users.update_one({"name": "test"}, {"$set": {"active": False}})
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        response = login(client, user, pwd)
        assert response.status_code == 200
        assert g.user == None
        assert b"Your login was expired." in response.data
        db.users.update_one({"name": "test"}, {"$set": {"active": True}})

def test_home_redirects_on_login_and_logout(client, app):
    """Test redirects on login and logout."""
    with app.app_context():
        # Prepare test database (set all users active)
        db = db_conn()[g.db_name]
        db.users.delete_one({"name": "fake"})
        db.users.update_many({}, {"$set": {"active": True}})

        # User with role=user login
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        response = login(client, user, pwd, False)
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/dashboard"

        # User with role=user logout
        response = logout(client, False)
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"
        
        # User with role=admin login
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        response = login(client, user, pwd, False)
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/admin"
        client.get("/")

        # User with role=admin logout
        response = logout(client, False)
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"

def test_home_login_errors(client, app):
    """Test user login errors."""
    with app.app_context():
        # Login not existing user
        user = "x"
        pwd = "x"
        response = login(client, user, pwd)
        assert response.status_code == 200
        assert b"User with such name does not exist." in response.data

        # Login existing user with wrong password
        user = app.config["USER_NAME"]
        pwd = "x"
        response = login(client, user, pwd)
        assert response.status_code == 200
        assert b"Incorrect password." in response.data

def test_home_content_for_logged_user(client, app):
    """Test home page content for logged user for redirection links."""
    with app.app_context():
        # Prepare test database (set all users active)
        db = db_conn()[g.db_name]
        db.users.delete_one({"name": "fake"})
        db.users.update_many({}, {"$set": {"active": True}})

        # Check page content
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        response = login(client, user, pwd)
        response = client.get("/")
        assert b'<a href="/dashboard">dashboard</a>' in response.data
        assert b'<a href="/logout">logout</a>' in response.data