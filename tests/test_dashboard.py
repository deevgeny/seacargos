from flask import g, session, get_flashed_messages
from seacargos.dashboard import (
    validate_user_input, check_db_records, tracking_status_content
)
from seacargos.db import db_conn

def test_dashboard_response(client, app):
    """Test dashboard for authenticated and not authenticated users."""
    with app.app_context():
        response = client.get("/dashboard")
        assert g.user == None
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        response = client.post(
            "/",
            data={"username": user, "password": pwd})
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/dashboard"

def test_validate_user_input(client, app):
    """Test validate user input function."""
    with app.app_context():
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        client.post(
            "/",
            data={"username": user, "password": pwd})
        client.get("/")
        assert g.user != None

        # Test booking number condition
        assert validate_user_input("OSAB12345678") == \
            {"bkgNo": "OSAB12345678", "line": "ONE",
            "user": "test", "trackEnd": None}
        assert validate_user_input("osab12345678") == \
            {"bkgNo": "OSAB12345678", "line": "ONE",
            "user": "test", "trackEnd": None}

        # Test container number condition
        assert validate_user_input("TCKU1234567") == \
            {"cntrNo": "TCKU1234567", "line": "ONE",
            "user": "test", "trackEnd": None}
        assert validate_user_input("tcku1234567") == \
            {"cntrNo": "TCKU1234567", "line": "ONE",
            "user": "test", "trackEnd": None}
        
        # Test wrong booking number condition len = 12
        with app.test_request_context("/dashboard"):
            assert validate_user_input("12345678OSAB") == \
                False
            assert get_flashed_messages() == \
                ["Incorrect booking or container number 12345678OSAB"]
        
        # Test wrong booking number condition len > 12
        with app.test_request_context("/dashboard"):
            assert validate_user_input("OSAB123456789") == \
                False
            assert get_flashed_messages() == \
                ["Incorrect booking or container number OSAB123456789"]
        with app.test_request_context("/dashboard"):
            # Test wrong booking number condition len < 11
            assert validate_user_input("TCKU123456") == \
                False
            assert get_flashed_messages() == \
                ["Incorrect booking or container number TCKU123456"]

def test_check_db_records(app):
    """Test check_db_records() function."""
    with app.app_context():
        db = db_conn()[g.db_name]

        # Check adding booking number
        query_bkg = {
            "bkgNo": "OSAB12345678", "line": "ONE",
            "user": "test", "trackEnd": None
            }
        assert check_db_records(query_bkg, db) == True
        db.tracking.insert_one(query_bkg)

        # Check flash message for booking number
        with app.test_request_context("/"):
            assert check_db_records(query_bkg, db) == False
            assert get_flashed_messages() == \
                ["Item OSAB12345678 already exists in tracking database."]
        db.tracking.delete_many({})

        # Check adding container number
        query_cntr = {
            "cntrNo": "TCKU1234567", "line": "ONE",
            "user": "test", "trackEnd": None
            }
        assert check_db_records(query_cntr, db) == True
        db.tracking.insert_one(query_cntr)

        # Check flash message for container number
        with app.test_request_context("/"):
            assert check_db_records(query_cntr, db) == False
            assert get_flashed_messages() == \
                ["Item TCKU1234567 already exists in tracking database."]
        
        # Clean database
        db.tracking.delete_many({})
    
def test_tracking_status_content(client, app):
    """Test tracking_status_content() function."""
    with app.app_context():
        db = db_conn()[g.db_name]

        # Check unauthenticated user request
        assert tracking_status_content(db) == False

        # Check authenticated user request
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        client.post(
            "/",
            data={"username": user, "password": pwd})
        client.get("/")
        assert tracking_status_content(db) == \
            {"active": 0, "arrived": 0, "total": 0}
        
        # Check total 1, active 1, arrived 0 condition
        db.tracking.insert_one({"user": "test", "trackEnd": None})
        assert tracking_status_content(db) == \
            {"active": 1, "arrived": 0, "total": 1}
        
        # Check total 1, active 1, arrived 1 condition
        db.tracking.insert_one({"user": "test", "trackEnd": "today"})
        assert tracking_status_content(db) == \
            {"active": 1, "arrived": 1, "total": 2}

        # Clean database
        db.tracking.delete_many({})
        
def test_db_tracking_data(client, app):
    """Test db_tracking_data() function."""
    pass

def test_schedule_table_data(client, app):
    """Test schedule_table_data() function."""
    pass