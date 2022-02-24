# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE


from flask import g, session, get_flashed_messages
from pymongo.mongo_client import MongoClient
from seacargos.db import db_conn
from seacargos.admin import size

# Helper functions to run tests
def login(client, user, pwd, follow=True):
    """Simple login function."""
    return client.post(
        "/", data={"username": user, "password": pwd},
        follow_redirects=follow)

def test_admin_response(client, app):
    """Test admin panel for authenticated and not authenticated users."""
    with app.app_context():
        # Not logged in user
        response = client.get("/admin")
        assert g.user == None
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"

        # Logged in user
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        response = login(client, user, pwd, False)
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/admin"
        response = login(client, user, pwd)
        assert response.status_code == 200
        
        # Wrong user role
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)
        response = client.get("/admin")
        assert response.status_code == 403
        assert b'You are not authorized to view this page.' in response.data

def test_size():
    """Test size() function."""
    assert size(1023) == "1023 bytes"
    assert size(1024) == "1.0 Kb"
    assert size(1048500) == "1023.9 Kb"
    assert size(1048576) == "1.0 Mb"
    assert size(1024**3 - 100000) == "1023.9 Mb"
    assert size(1024**3) == "1.0 Gb"













































