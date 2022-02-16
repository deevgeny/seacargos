# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from pymongo.mongo_client import MongoClient
from datetime import datetime
from datetime import timedelta

from seacargos.etl.oneline_update import log
from seacargos.etl.oneline_update import records_to_update
from seacargos.etl.oneline_update import extract_schedule_details
from seacargos.etl.oneline_update import str_to_date
from seacargos.etl.oneline_update import transform

def test_log():
    """Test log() function."""
    # Write test log
    log("test log")
    # Read test log
    with open("etl.log", "r") as f:
        log_data =f.read().split("\n")
    # Check test log
    check = log_data[-1].split(" ")
    assert len(check) == 4
    assert len(check[0]) == 10
    assert len(check[1]) == 8
    assert check[2] == "test"
    assert check[3] == "log"

def test_records_to_update(app):
    """Test records_to_update() function."""
    with app.app_context():
        # Prepare variables and clean database
        uri = app.config["DB_FRONTEND_URI"]
        db_name = app.config["DB_NAME"]
        conn = MongoClient(uri)
        db = conn[db_name]
        db.tracking.delete_many({})

        # Connection failure condition
        #bad_uri = uri.replace("27017", "27016")
        #bad_conn = MongoClient(bad_uri)
        #result = records_to_update(bad_conn, db)
        #assert result == False
        #with open("etl.log", "r") as f:
        #    check = f.read().split("\n")
        #assert "[oneline_update.py] [records_to_update()] "\
        #    + "[DB Connection failure]" in check[-1]

        # Base exception condition
        bad_uri = uri.replace("<", ">")
        bad_conn = MongoClient(bad_uri)
        result = records_to_update(bad_conn, db)
        assert result == False
        with open("etl.log", "r") as f:
            check = f.read().split("\n")
        assert "Authentication failed." in check[-1]
        
        # Empty db, no user, no bkg_number condition check
        result = records_to_update(conn, db)
        assert result == False
        with open("etl.log", "r") as f:
            check = f.read().split("\n")
        assert "Nothing to update for query" in check[-1]

        # Write test data set to database
        one_day = timedelta(days=1)
        records = [
            {"trackEnd": None, "user": 1, "bkgNo": 1, "copNo": 1,
            "schedule": [
                {"status": "E", "eventDate": datetime.now() - one_day}
                ]
            },
            {"trackEnd": None, "user": 2, "bkgNo": 2, "copNo": 2,
            "schedule": [
                {"status": "E", "eventDate": datetime.now() - one_day}
                ]
            },
            {"trackEnd": None, "user": 1, "bkgNo": 3, "copNo": 3,
            "schedule": [
                {"status": "A", "eventDate": datetime.now() - one_day}
                ]
            },
            {"trackEnd": None, "user": 2, "bkgNo": 4, "copNo": 4,
            "schedule": [
                {"status": "E", "eventDate": datetime.now() + one_day}
                ]
            },
            {"trackEnd": "end", "user": 1, "bkgNo": 5, "copNo": 5,
            "schedule": [
                {"status": "E", "eventDate": datetime.now() - one_day}
                ]
            }
        ]
        db.tracking.insert_many(records)

        # No user and bkg_number arguments (filter by schedule element match)
        result = records_to_update(conn, db)
        assert len(result) == 2
        assert result == [{"bkgNo": 1, "copNo": 1}, {"bkgNo": 2, "copNo": 2}]

        # user argument condition check (get all user records)
        result = records_to_update(conn, db, user=1)
        assert len(result) == 2
        assert result == [
            {"bkgNo": 1, "copNo": 1, "user": 1},
            {"bkgNo": 3, "copNo": 3, "user": 1}
            ]

        result = records_to_update(conn, db, user=2)
        assert len(result) == 2
        assert result == [
            {"bkgNo": 2, "copNo": 2, "user": 2},
            {"bkgNo": 4, "copNo": 4, "user": 2}
            ]

        # user and bkg_number arguments condition check (get one user record)
        result = records_to_update(conn, db, user=1, bkg_number=3)
        assert len(result) == 1
        assert result == [{"bkgNo": 3, "copNo": 3, "user": 1}]

        result = records_to_update(conn, db, user=2, bkg_number=4)
        assert len(result) == 1
        assert result == [{"bkgNo": 4, "copNo": 4, "user": 2}]

        # Close connection and clean database
        db.tracking.delete_many({})
        conn.close()

def test_extract_schedule_details():
    """Test extract_schedule_details() function."""
    # Pass False argument to the function
    result = extract_schedule_details(False)
    assert result == False

    # Pass list of records to the function
    records = [
        {"bkgNo": "OSAB76633400", "copNo": "COSA1C20995300"},
        {"bkgNo": "OSAB76636700", "copNo": "COSA1C20995104"}
    ]
    result = extract_schedule_details(records)
    assert len(result) == 2
    assert "schedule" in result[0]
    assert "schedule" in result[1]
    assert "hashColumns" not in result[0]["schedule"][0]

    # Pass list of incorrect records to the function
    records = [
        {"bkgNo": "OSAB7663340", "copNo": "COSA1C2099530"},
        {"bkgNo": "OSAB7663670", "copNo": "COSA1C2099510"}
    ]
    result = extract_schedule_details(records)
    assert len(result) == 2
    assert "schedule" in result[0]
    assert "schedule" in result[1]
    assert result[0]["schedule"] == None
    assert result[1]["schedule"] == None
    with open("etl.log", "r") as f:
        check = f.read().split("\n")
    assert "[oneline_update.py] [extract_schedule_details()]"\
                + f" [No schedule for {records[0]['bkgNo']}]" in check[-2]
    assert "[oneline_update.py] [extract_schedule_details()]"\
                + f" [No schedule for {records[1]['bkgNo']}]" in check[-1]

def test_str_to_date():
    """Test str_to_date() function."""
    # Check short string
    result = str_to_date("")
    assert result.year == 1970

    # Check correct string
    result = str_to_date("2022-12-01 10:09")
    assert result.year == 2022
    assert result.month == 12
    assert result.day == 1 
    assert result.hour == 10
    assert result.minute == 9

def test_transform():
    """Test transform() function."""
    # Pass False argument to the function
    result = transform(False)
    assert result == False