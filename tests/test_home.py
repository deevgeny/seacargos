from werkzeug.utils import redirect
from seacargos import create_app
from flask import g, session
from seacargos.db import setup_db

def test_home(client, app):
    """Test home page for unauthenticated user."""
    with app.app_context():
        response = client.get("/")
        assert response.status_code == 200
        assert g.user == None

def test_home_login_valid_user(client, app):
    """Test user login."""
    with app.app_context():
        #setup_db(app)
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        response = client.post(
            "/",
            data={"username": user, "password": pwd})
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/dashboard"

def test_home_login_invalid_user(client, app):
    """Test user login."""
    with app.app_context():
        #setup_db(app)
        user = "x"
        pwd = "x"
        response = client.post(
            "/",
            data={"username": user, "password": pwd})
        assert response.status_code == 200

def test_logout_valid_user(client, app):
    """Test logout valid user."""
    with app.app_context():
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        response = client.post(
            "/",
            data={"username": user, "password": pwd})
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/dashboard"
        response = client.get("/logout")
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"
