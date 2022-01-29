# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022  Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from flask import g, session, get_flashed_messages
from pymongo.mongo_client import MongoClient
from seacargos.dashboard import (
    validate_user_input, check_db_records, tracking_summary,
    db_tracking_data, schedule_table_data, ping, db_get_record,
    prepare_record_details
)
from seacargos.db import db_conn
import json
from bson.json_util import dumps
from datetime import datetime
from seacargos.etl.oneline import etl_one
BKG_NO_1 = "OSAB67971900"
BKG_NO_2 = "OSAB76049500"

# Helper functions to run tests
def login(client, user, pwd, follow=True):
    """Simple login function."""
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
            "/dashboard", data={"booking": BKG_NO_1, "refId": ""},
            follow_redirects=True)
        assert b"New record successfully added to database" in response.data

        # Try to add duplicated record 
        response = client.post(
            "/dashboard", data={"booking": BKG_NO_1, "refId": ""},
            follow_redirects=True)
        assert b"Item OSAB67971900 already exists in tracking database." in \
            response.data

        # Clean database after tests
        db.tracking.delete_many({})
 
def test_details(client, app):
    """Test details view.."""
    with app.app_context():
        # Not logged user
        response = client.get(f"/dashboard/{BKG_NO_1}")
        assert g.user == None
        assert response.status_code == 302
        assert response.headers["Location"] == "http://localhost/"

        # Logged in user check not existing record
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)
        response = client.get(f"/dashboard/{BKG_NO_1}")
        assert response.status_code == 200
        assert b'Record OSAB67971900 not found in database.' in response.data

        # Logged in user check existing record
        conn = db_conn()
        db = conn[g.db_name]
        query = {"bkgNo": BKG_NO_1, "line": "ONE",
                 "user": g.user["name"], "trackEnd": None, "refId": "-"} 
        etl_one(query, conn, db)
        response = client.get(f"/dashboard/{BKG_NO_1}")
        assert response.status_code == 200
        assert b'Details for OSAB67971900' in response.data

        # Clear test database
        db.tracking.delete_many({})

def test_update(app, client):
    """Test update() view."""
    with app.app_context():
        db = db_conn()[g.db_name]
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)
        # Prepare booking number 1 test data
        client.post(
            "/dashboard", data={"booking": BKG_NO_1, "refId": ""},
            follow_redirects=True)
        rec = db.tracking.find_one({"bkgNo": BKG_NO_1})
        bkg_no_1 = {
            "recordUpdate": rec["recordUpdate"],
            "regularUpdate": rec["regularUpdate"]
        }
        # Prepare booking number 2 test data
        client.post(
            "/dashboard", data={"booking": BKG_NO_2, "refId": ""},
            follow_redirects=True)
        rec = db.tracking.find_one({"bkgNo": BKG_NO_1})
        bkg_no_2 = {
            "recordUpdate": rec["recordUpdate"],
            "regularUpdate": rec["regularUpdate"]
        }
        # Update all records in database
        client.get("/dashboard/update", follow_redirects=True)
        # Check booking number 1 record
        rec = db.tracking.find_one({"bkgNo": BKG_NO_1})
        assert rec["recordUpdate"] == rec["regularUpdate"]
        assert rec["recordUpdate"] > bkg_no_1["recordUpdate"]
        assert rec["regularUpdate"] > bkg_no_1["regularUpdate"]
        # Check booking number 2 record
        rec = db.tracking.find_one({"bkgNo": BKG_NO_2})
        assert rec["recordUpdate"] == rec["regularUpdate"]
        assert rec["recordUpdate"] > bkg_no_2["recordUpdate"]
        assert rec["regularUpdate"] > bkg_no_2["regularUpdate"]
        db.tracking.delete_many({})

def test_update_record(app, client):
    """Test update_record() view."""
    with app.app_context():
        db = db_conn()[g.db_name]
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)
        # Load record to db
        client.post(
            "/dashboard", data={"booking": BKG_NO_1, "refId": ""},
            follow_redirects=True)
        # Update record
        client.get(f"/dashboard/update/{BKG_NO_1}", follow_redirects=True)
        rec = db.tracking.find_one({"bkgNo": BKG_NO_1})
        assert rec["recordUpdate"] > rec["regularUpdate"]
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

        # Login
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)

        # Check empty database
        assert tracking_summary(db, user) == \
            {"active": 0, "arrived": 0, "total": 0, "updated_on": "-"}
        
        # Check total 1, active 1, arrived 0, last_update 2 condition
        date_1 = datetime(2022, 1, 20, 00, 00, 00)
        db.tracking.insert_one(
            {"user": "test", "trackEnd": None, "regularUpdate": date_1}
            )
        assert tracking_summary(db, user) == \
            {"active": 1, "arrived": 0, "total": 1,
            "updated_on": "20-01-2022 00:00"}
        
        # Check total 2, active 1, arrived 1, last_update 2 condition
        date_2 = datetime(2022, 1, 25, 00, 00, 00)
        db.tracking.insert_one(
            {"user": "test", "trackEnd": date_2, "regularUpdate": date_2})
        assert tracking_summary(db, user) == \
            {"active": 1, "arrived": 1, "total": 2,
            "updated_on": "20-01-2022 00:00"}
        
        # Check total 3, active 2, arrived 1, last_update 1 condition
        db.tracking.insert_one(
            {"user": "test", "trackEnd": None, "regularUpdate": date_2}
            )
        assert tracking_summary(db, user) == \
            {"active": 2, "arrived": 1, "total": 3,
            "updated_on": "25-01-2022 00:00"}

        # Clean database
        db.tracking.delete_many({})
        
def test_db_tracking_data(client, app):
    """Test db_tracking_data() function."""
    with app.app_context():
        # Check unauthenticated user - deprication
        db = db_conn()[g.db_name]
        #assert db_tracking_data(None, db) == False

        # Check authenticated user and empty db
        user = app.config["USER_NAME"]
        pwd = app.config["USER_PASSWORD"]
        login(client, user, pwd)
        cursor = db.tracking.aggregate(
            [{"$match": {"user": user, "trackEnd": None}},
            {"$sort": {"departureDate": -1}},
            {"$project": {"_id": 0, "schedule": 0, "initSchedule": 0}}]
        )
        ln = len(json.loads(dumps(cursor)))
        check = len(json.loads(dumps(db_tracking_data(g.user["name"], db))))
        assert check == ln

        # Check authenticated user and not empty db
        record = {'cntrNo': 'SZLU3605702', 'cntrType': "20'REEFER",
            'copNo': 'COSA1B09517221', 'bkgNo': 'OSAB67971900',
            'blNo': 'OSAB67971900', 'user': 'test', 'line': 'ONE',
            'trackStart': datetime(2021, 12, 1, 7, 42), 'trackEnd': None,
            'outboundTerminal': 'NAGOYA, AICHI, JAPAN|TCB',
            'departureDate': datetime(2021, 12, 1, 7, 42),
            'inboundTerminal': 'ST PETERSBURG, RUSSIAN FEDERATION|JSC',
            'arrivalDate': datetime(2021, 12, 1, 7, 42), 'vesselName': None,
            'location': None}
        db.tracking.insert_one(record)
        record.pop("_id", None)
        cursor = db.tracking.aggregate(
            [{"$match": {"user": user, "trackEnd": None}},
            {"$sort": {"departureDate": -1}},
            {"$project": {"_id": 0, "schedule": 0, "initSchedule": 0}}]
        )
        ln = len(json.loads(dumps(cursor)))
        check = len(json.loads(dumps(db_tracking_data(g.user["name"], db))))
        assert check == ln

        # Clear db
        db.tracking.delete_many({})
            

def test_schedule_table_data():
    """Test schedule_table_data() function."""
    records = [{'cntrNo': 'SZLU3605702', 'refId': '-', 'cntrType': "20'REEFER",
            'copNo': 'COSA1B09517221', 'bkgNo': 'OSAB67971900',
            'blNo': 'OSAB67971900', 'user': 'test', 'line': 'ONE',
            'trackStart': datetime(2021, 12, 1, 7, 42), 'trackEnd': None,
            'outboundTerminal': 'NAGOYA, AICHI, JAPAN|TCB',
            'departureDate': datetime(2021, 12, 1, 7, 42),
            'inboundTerminal': 'ST PETERSBURG, RUSSIAN FEDERATION|JSC',
            'arrivalDate': datetime(2021, 12, 10, 10, 0), 'vesselName': None,
            'location': None}]
    table = {"table": [
        {"booking": "OSAB67971900", "refId": "-", "container": "SZLU3605702",
         "type": "20'REEFER", 
         "from": {"location": "NAGOYA, AICHI, JAPAN", "terminal": "TCB"},
         "departure": "01-12-2021 07:42",
         "to": {"location": "ST PETERSBURG, RUSSIAN FEDERATION",
                "terminal": "JSC"},
         "arrival": "10-12-2021 10:00",
         "totalDays": 9}
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

def test_db_get_record(app):
    """Test db_get_record() function."""
    with app.app_context():
        conn = db_conn()
        db = conn[g.db_name]
        # Check empty database
        assert db_get_record(db, BKG_NO_1, "test") == None

        # Check non empty database condition
        user = app.config["USER_NAME"]
        query = {"bkgNo": BKG_NO_1, "line": "ONE",
                 "user": user, "trackEnd": None, "refId": "-"} 
        etl_one(query, conn, db)
        record =  db_get_record(db, BKG_NO_1, "test")
        assert record != None
        assert isinstance(record, dict) == True 

        # Clear test database
        db.tracking.delete_many({})

def test_prepare_record_details(app):
    """Test prepare_record_details() function."""
    with app.app_context():
        # Check empty db condition
        assert prepare_record_details(None) == None

        # Check non empty db condition
        conn = db_conn()
        db = conn[g.db_name]
        user = app.config["USER_NAME"]
        query = {"bkgNo": BKG_NO_1, "line": "ONE",
                 "user": user, "trackEnd": None, "refId": "-"} 
        etl_one(query, conn, db)
        record =  db_get_record(db, BKG_NO_1, "test")
        details = prepare_record_details(record)
        keys = ["event", "placeName", "yardName", "plannedDate",
                "actualDate", "delta", "status"]
        assert details != None
        assert isinstance(details, list) == True
        assert set(keys).issubset(set(details[0].keys())) == True

        # Clear test database
        db.tracking.delete_many({})




        