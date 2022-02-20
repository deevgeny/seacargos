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
from seacargos.etl.oneline_update import update

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
    assert "bkgNo" in result[0]
    assert "copNo" in result[0]
    assert "schedule" in result[1]
    assert "bkgNo" in result[1]
    assert "copNo" in result[1]
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
    # Prepare test data
    records = [
        {"bkgNo": "OSAB76633400", "copNo": "COSA1C20995300"},
    ]

    # Pass False argument to the function
    result = transform(False)
    assert result == False

    # Pass raw data with correct keys to the function
    raw = extract_schedule_details(records)
    result = transform(raw)
    keys = [
        "no", "event", "placeName", "yardName", "eventDate", "status",
        "vesselName", "imo"]
    assert set(keys).difference(set(result[0]["schedule"][0])) == set()
    terminals = [
        "departureDate", "outboundTerminal", "arrivalDate", "inboundTerminal"
        ]
    assert set(terminals).issubset(set(result[0]))

    # Check datatypes
    assert isinstance(result[0]["departureDate"], datetime)
    assert isinstance(result[0]["outboundTerminal"], str)
    assert isinstance(result[0]["arrivalDate"], datetime)
    assert isinstance(result[0]["inboundTerminal"], str)
    assert isinstance(result[0]["schedule"][0]["no"], int)
    assert isinstance(result[0]["schedule"][0]["event"], str)
    assert isinstance(result[0]["schedule"][0]["placeName"], str)
    assert isinstance(result[0]["schedule"][0]["yardName"], str)
    assert isinstance(result[0]["schedule"][0]["eventDate"], datetime)
    assert isinstance(result[0]["schedule"][0]["status"], str)
    assert isinstance(result[0]["schedule"][0]["vesselName"], str)
    assert isinstance(result[0]["schedule"][0]["imo"], str)

    # Check actual data vs raw data for one schedule record item
    raw = extract_schedule_details(records)
    check = raw[0]["schedule"][0]
    result = transform(raw)
    assert result[0]["schedule"][0]["no"] == int(check["no"])
    assert result[0]["schedule"][0]["event"] == check["statusNm"]
    assert result[0]["schedule"][0]["placeName"] == check["placeNm"]
    assert result[0]["schedule"][0]["yardName"] == check["yardNm"]
    assert result[0]["schedule"][0]["eventDate"] == str_to_date(check["eventDt"])
    assert result[0]["schedule"][0]["status"] == check["actTpCd"]
    assert result[0]["schedule"][0]["vesselName"] == check["vslEngNm"]
    assert result[0]["schedule"][0]["imo"] == check["lloydNo"]

    # Pass raw data with missing keys to the function
    raw = extract_schedule_details(records)
    raw[0]["schedule"][0].pop("no")
    result = transform(raw)
    assert result[0]["schedule"] == None
    with open("etl.log", "r") as f:
        check = f.read().split("\n")
    assert "[oneline_update.py] [transform()] [Keys do not match"\
                + f" in schedule data {records[0]['bkgNo']}]" in check[-1]

def test_update(app):
    """Test update() function."""
    with app.app_context():
        # Prepare variables and clean database
        uri = app.config["DB_FRONTEND_URI"]
        db_name = app.config["DB_NAME"]
        conn = MongoClient(uri)
        db = conn[db_name]
        db.tracking.delete_many({})   

        # Pass False argument to the function
        result = update(conn, db, False)
        assert result == False

        # Run with regular_update=True condition
        db_record = {
            "bkgNo": "OSAB76633400",
            "copNo": "COSA1C20995300",
            "trackEnd": None,
            "schedule": None,
            "user": "test",
            "departureDate": None,
            "outboundTerminal": None,
            "arrivalDate": None,
            "inboundTerminal": None,
            "regularUpdate": None,
            "recordUpdate": None
        }
        db.tracking.insert_one(db_record)
        records = [
            {"bkgNo": "OSAB76633400",
            "copNo": "COSA1C20995300",
            "user": "test"},
        ]
        raw = extract_schedule_details(records)
        result = transform(raw)
        update(conn, db, result)
        check = db.tracking.find_one({})
        assert check["user"] == result[0]["user"]
        assert check["schedule"] == result[0]["schedule"]
        assert check["departureDate"] == result[0]["departureDate"]
        assert check["outboundTerminal"] == result[0]["outboundTerminal"]
        assert check["arrivalDate"] == result[0]["arrivalDate"]
        assert check["inboundTerminal"] == result[0]["inboundTerminal"]
        assert isinstance(check["recordUpdate"], datetime)
        assert isinstance(check["regularUpdate"], datetime)
        assert check["recordUpdate"] == check["regularUpdate"]
        db.tracking.delete_many({})

        # Run with reqular_update=False condition
        db.tracking.insert_one(db_record)
        records = [
            {"bkgNo": "OSAB76633400",
            "copNo": "COSA1C20995300",
            "user": "test"},
        ]
        raw = extract_schedule_details(records)
        result = transform(raw)
        update(conn, db, result, regular_update=False)
        check = db.tracking.find_one({})
        assert check["user"] == result[0]["user"]
        assert check["schedule"] == result[0]["schedule"]
        assert check["departureDate"] == result[0]["departureDate"]
        assert check["outboundTerminal"] == result[0]["outboundTerminal"]
        assert check["arrivalDate"] == result[0]["arrivalDate"]
        assert check["inboundTerminal"] == result[0]["inboundTerminal"]
        assert isinstance(check["recordUpdate"], datetime)
        assert not isinstance(check["regularUpdate"], datetime)
        db.tracking.delete_many({})
        
        # Run with record["schedule"]=None condition (error log write check)
        db.tracking.insert_one(db_record)
        records = [
            {"bkgNo": "OSAB76633400",
            "copNo": "COSA1C20995300",
            "user": "test"},
        ]
        raw = extract_schedule_details(records)
        result = transform(raw)
        result[0]["schedule"] = None
        update(conn, db, result)
        check = db.tracking.count_documents({})
        with open("etl.log", "r") as f:
            check = f.read().split("\n")
        assert "[oneline_update.py] [update()] "\
            + f"[{result[0]['bkgNo']} not updated in database]" in check[-1]
        db.tracking.delete_many({})
        
        # Test db query user validation & update condition
        db.tracking.insert_one(db_record)
        records = [
            {"bkgNo": "OSAB76633400",
            "copNo": "COSA1C20995300",
            "user": "test"},
        ]
        raw = extract_schedule_details(records)
        result = transform(raw)
        result[0].pop("user") # Remove user to check
        result[0]["departureDate"] = "new data"
        result[0]["outboundTerminal"] = "new data"
        result[0]["arrivalDate"] = "new data"
        result[0]["inboundTerminal"] = "new data"
        update(conn, db, result)
        check = db.tracking.find_one({})
        assert check["schedule"] == result[0]["schedule"]
        assert check["departureDate"] == result[0]["departureDate"]
        assert check["outboundTerminal"] == result[0]["outboundTerminal"]
        assert check["arrivalDate"] == result[0]["arrivalDate"]
        assert check["inboundTerminal"] == result[0]["inboundTerminal"]
        assert isinstance(check["recordUpdate"], datetime)
        assert isinstance(check["regularUpdate"], datetime)
        db.tracking.delete_many({})

        # Test update["$set"] modification by func
        db.tracking.insert_one(db_record)
        records = [
            {"bkgNo": "OSAB76633400",
            "copNo": "COSA1C20995300",
            "user": "test"},
        ]
        raw = extract_schedule_details(records)
        result = transform(raw)
        result[0].pop("departureDate")
        result[0].pop("outboundTerminal")
        result[0].pop("arrivalDate")
        result[0].pop("inboundTerminal")
        update(conn, db, result)
        check = db.tracking.find_one({})
        assert check["departureDate"] == None
        assert check["outboundTerminal"] == None
        assert check["arrivalDate"] == None
        assert check["inboundTerminal"] == None
        assert isinstance(check["recordUpdate"], datetime)
        assert isinstance(check["regularUpdate"], datetime)
        db.tracking.delete_many({})

        # Clean database and close connection
        db.tracking.delete_many({})
        conn.close()
        