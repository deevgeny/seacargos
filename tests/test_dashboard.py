from flask import g, session, get_flashed_messages
from pymongo.mongo_client import MongoClient
from seacargos.dashboard import (
    validate_user_input, check_db_records, tracking_summary,
    db_tracking_data, schedule_table_data, ping
)
from seacargos.db import db_conn

# Helper functions for running tests
def login(client, user, pwd, follow=True):
    return client.post(
        "/", data={"username": user, "password": pwd},
        follow_redirects=follow)

# View tests
def test_dashboard_response(client, app):
    """Test dashboard for authenticated and not authenticated users."""
    with app.app_context():
        # Not logged user
        response = client.get("/dashboard")
        assert g.user == None
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"

        # Logged in user check redirects
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        response = login(client, user, pwd, False)
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/dashboard"

        # Wrong user role
        user = app.config["ADMIN_NAME"]
        pwd = app.config["ADMIN_PASSWORD"]
        login(client, user, pwd)
        response = client.get("/dashboard")
        assert response.status_code == 403
        assert b'You are note authorized to view this page.' in response.data

def test_dashboard_input_form(client, app):
    """Test dashboard input form."""
    with app.app_context():
        # Login and add new record
        db = db_conn()[g.db_name]
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)
        response = client.post(
            "/dashboard", data={"booking": "OSAB67987900"},
            follow_redirects=True)
        assert b"New record successfully added to database" in response.data

        # Try to add duplicated record 
        response = client.post(
            "/dashboard", data={"booking": "OSAB67987900"},
            follow_redirects=True)
        assert b"Item OSAB67987900 already exists in tracking database." in \
            response.data

        # Clean database after tests
        db.tracking.delete_many({})
 

# Helper functions tests
def test_validate_user_input(client, app):
    """Test validate user input function."""
    with app.app_context():
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)
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
        # Check no query condition
        assert check_db_records(None, db) == False

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
    
def test_tracking_summary(client, app):
    """Test tracking_status_content() function."""
    with app.app_context():
        db = db_conn()[g.db_name]

        # Check unauthenticated user request
        assert tracking_summary(db) == False

        # Check authenticated user request
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)
        assert tracking_summary(db) == \
            {"active": 0, "arrived": 0, "total": 0}
        
        # Check total 1, active 1, arrived 0 condition
        db.tracking.insert_one({"user": "test", "trackEnd": None})
        assert tracking_summary(db) == \
            {"active": 1, "arrived": 0, "total": 1}
        
        # Check total 1, active 1, arrived 1 condition
        db.tracking.insert_one({"user": "test", "trackEnd": "today"})
        assert tracking_summary(db) == \
            {"active": 1, "arrived": 1, "total": 2}

        # Clean database
        db.tracking.delete_many({})
        
def test_db_tracking_data(client, app):
    """Test db_tracking_data() function."""
    with app.app_context():
        # Check unauthenticated user
        db = db_conn()[g.db_name]
        assert db_tracking_data(None, db) == False

        # Check authenticated user and empty db
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)
        assert db_tracking_data(g.user["name"], db) == []

        # Check authenticated user and not empty db
        record = {'cntrNo': 'SZLU3605702', 'cntrType': "20'REEFER",
            'copNo': 'COSA1B09517221', 'bkgNo': 'OSAB67971900',
            'blNo': 'OSAB67971900', 'user': 'test', 'line': 'ONE',
            'trackStart': {'$date': 1641484241000}, 'trackEnd': None,
            'outboundTerminal': 'NAGOYA, AICHI, JAPAN|TCB',
            'departureDate': {'$date': 1641702600000},
            'inboundTerminal': 'ST PETERSBURG, RUSSIAN FEDERATION|JSC',
            'arrivalDate': {'$date': 1645243200000}, 'vesselName': None,
            'location': None}
        db.tracking.insert_one(record)
        record.pop("_id", None)
        assert db_tracking_data(g.user["name"], db) == [record]

        # Clear db
        db.tracking.delete_many({})
            

def test_schedule_table_data():
    """Test schedule_table_data() function."""
    records = [{'cntrNo': 'SZLU3605702', 'cntrType': "20'REEFER",
            'copNo': 'COSA1B09517221', 'bkgNo': 'OSAB67971900',
            'blNo': 'OSAB67971900', 'user': 'test', 'line': 'ONE',
            'trackStart': {'$date': 1641484241000}, 'trackEnd': None,
            'outboundTerminal': 'NAGOYA, AICHI, JAPAN|TCB',
            'departureDate': {'$date': 1641702600000},
            'inboundTerminal': 'ST PETERSBURG, RUSSIAN FEDERATION|JSC',
            'arrivalDate': {'$date': 1645243200000}, 'vesselName': None,
            'location': None}]
    table = {"table": [
        {"booking": "OSAB67971900", "container": "SZLU3605702",
         "type": "20'REEFER", 
         "from": {"location": "NAGOYA, AICHI, JAPAN", "terminal": "TCB"},
         "departure": "09-01-2022 07:30",
         "to": {"location": "ST PETERSBURG, RUSSIAN FEDERATION",
                "terminal": "JSC"},
         "arrival": "19-02-2022 07:00",
         "totalDays": 40}
        ]}
    assert schedule_table_data(records) == table

def test_ping_decorator_function(app):
    """Test ping function."""
    with app.app_context():
        # Prepare test function
        @ping
        def run_ping(conn):
            conn.admin.command("ping")
            return True

        # Prepare connections
        conn = db_conn()
        bad_uri = app.config["DB_FRONTEND_URI"].replace("147", "146")
        bad_conn = MongoClient(bad_uri)

        # Check good connection
        assert run_ping(conn) == True

        # Check for ConnectionFailure error
        #assert run_ping(bad_conn) == False

        # Check BaseException error
        assert run_ping(None) == False
