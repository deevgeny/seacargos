#!/usr/bin/env python3
# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

import requests
import json
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.json_util import dumps
import sys
import os

URL = "https://ecomm.one-line.com/ecom/CUP_HOM_3301GS.do"

# ETL functions
def log(message):
    """Log function to log errors."""
    timestamp = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
    with open("etl.log", "a") as f:
        f.write("\n" + timestamp + " " + message)

def records_to_update(conn, db, user=None, bkg_number=None):
    """Prepare records which require update."""
    # Check function args
    project = {"user": 1, "bkgNo": 1, "copNo": 1, "_id": 0}
    if user and bkg_number:
        query = {"trackEnd": None, "user": user, "bkgNo": bkg_number}
    elif user:
        query = {"trackEnd": None, "user": user}
    else:  
        now = datetime.now().replace(microsecond=0)
        query = {
            "trackEnd": None,
            "schedule": {"$elemMatch": {
                "status": "E", "eventDate": {"$lte": now}
                }
            }
        }
        project.pop("user")
    # Run query
    try:
        conn.admin.command("ping")
        cur = db.tracking.find(query, project)
        records = json.loads(dumps(cur))
        if len(records) > 0:
            return records
        else:
            log("[oneline_update.py] [records_to_update()] "\
                + f"[Nothing to update for query {query}]")
            return False
    except ConnectionFailure:
        log("[oneline_update.py] [records_to_update()] "\
            + "[DB Connection failure]")
        return False
    except BaseException as err:
        log("[oneline_update.py] [records_to_update()] "\
            + f"[{err.details}]")
        return False

def extract_schedule_details(records):
    """Extract schedule details for update."""
    # Check input
    if not records:
        return False
    # Extract data
    for rec in records:
        # Create payload
        payload = {
            '_search': 'false', 'f_cmd': '125', 'cntr_no': "",
            'bkg_no': rec["bkgNo"], 'cop_no': rec["copNo"]
        }
        # Run request and fetch json data
        r = requests.get(URL, params=payload)
        data = r.json()
        # Get schedule, clean and add to record
        if "list" in data:
            schedule_details = data["list"]
            schedule_details[0].pop("hashColumns", None)
            rec["schedule"] = schedule_details
        else:
            log("[oneline_update.py] [extract_schedule_details()]"\
                + f" [No schedule for {rec['bkgNo']}]")
            rec["schedule"] = None
    return records

def str_to_date(string):
        """Convert string to date."""
        if len(string) == 16:
            return datetime.strptime(string, "%Y-%m-%d %H:%M")
        else:
            return datetime.fromtimestamp(0)

def transform(records):
    """Transforms raw data."""
    # Check input
    if not records:
        return False
    
    # Check schedule keys and extract schedule data
    schedule_keys = ["no", "statusNm", "placeNm", "yardNm",
                     "eventDt", "actTpCd", "actTpCd", "vslEngNm",
                     "lloydNo"]
    for rec in records:
        if set(schedule_keys).issubset(set(rec["schedule"][0])):
            transformed_schedule = []
            for i in rec["schedule"]:
                transformed_schedule.append(
                    {"no": int(i["no"]),
                     "event": i["statusNm"],
                     "placeName": i["placeNm"],
                     "yardName": i["yardNm"],
                     "eventDate": str_to_date(i["eventDt"]),
                     "status": i["actTpCd"],
                     "vesselName": i["vslEngNm"],
                     "imo": i["lloydNo"]}
                )
                # Update arr/dep dates and terminals
                if i["statusNm"].find("Departure from Port of Loading") > -1: 
                    rec["departureDate"] = str_to_date(i["eventDt"])
                    rec["outboundTerminal"] = i["placeNm"]\
                        + "|" + i["yardNm"]
                if i["statusNm"].find("Arrival at Port of Discharging") > -1:
                    rec["arrivalDate"] = str_to_date(i["eventDt"])
                    rec["inboundTerminal"] = i["placeNm"]\
                        + "|" + i["yardNm"]
            rec["schedule"] = transformed_schedule
        else:
            log("[oneline_update.py] [transform()] "\
                + f"[Keys do not match in schedule data {rec['bkgNo']}]")
            rec["schedule"] = None
    return records

def update(conn, db, records, regular_update=True):
    """Update records in database."""
    # Check function args
    if not records:
        return False

    # Prepare reusable parameters
    timestamp = datetime.now().replace(microsecond=0)
    query = {"bkgNo": None, "trackEnd": None}
    update = {"$set": {
        "schedule": None,
        "recordUpdate": timestamp
        }
    }
    if regular_update:
        update["$set"]["regularUpdate"] = timestamp
    
    # Start update
    try:
        conn.admin.command("ping")
        for rec in records:
            if rec["schedule"]:
                query["bkgNo"] = rec["bkgNo"]
                update["$set"]["schedule"] = rec["schedule"]
                if "user" in rec:
                    query["user"] = rec["user"]
                if "departureDate" in rec:
                    update["$set"]["departureDate"] = rec["departureDate"]
                if "outboundTerminal" in rec:
                    update["$set"]["outboundTerminal"] = rec["outboundTerminal"]
                if "arrivalDate" in rec:
                    update["$set"]["arrivalDate"] = rec["arrivalDate"]
                if "inboundTerminal" in rec:
                    update["$set"]["inboundTerminal"] = rec["inboundTerminal"]
                cursor = db.tracking.update_one(query, update)
                if cursor.acknowledged == False:
                    log("[oneline_update.py] [update()] "\
                    + f"[{rec['bkgNo']} not updated for {rec.get('user', None)}]")
            else:
                log("[oneline_update.py] [update()] "\
                + f"[Not updated {rec['bkgNo']}]")
    except ConnectionFailure:
        log(f"[oneline_update.py] [update()] [Connection failure]")
    except BaseException as err:
        log(f"[oneline_update.py] [update()] [{err}]")

def arrived(conn, db, user=None):
    """Find containers which arrived to destination."""
    # Check function args
    if user:
        query = {"trackEnd": None, "user": user}
    else:
        query = {"trackEnd": None}
    # Query database
    try:
        conn.admin.command("ping")
        cur = db.tracking.aggregate([
            {"$match": query},
            {"$addFields": {"last": {"$last": "$schedule"}}},
            {"$match": {"last.status": "A" }},
            {"$project": {"bkgNo": 1, "_id": 0}}
        ])
        records = json.loads(dumps(cur))
        if len(records) > 0:
            return records
        else:
            return False
    except ConnectionFailure:
        log("[oneline_update.py] [arrived()] "\
            + f"[DB Connection failure]")
        return False
    except BaseException as err:
        log("[oneline_update.py] [arrived()] "\
            + f"[{err.details}]")
        return False
    
def track_end(conn, db, records):
    """Set trackEnd field in database to current date and time."""
    # Check function args
    if not records:
        return False
    # Run update
    try:
        conn.admin.command("ping")
        query = {"bkgNo": None, "trackEnd": None}
        for rec in records:
            query["bkgNo"] = rec["bkgNo"]
            cur = db.tracking.update_one(
                query,
                {"$set": {"trackEnd": datetime.now().replace(microsecond=0)}},
            )
            if cur.acknowledged == False:
                log("[oneline_update.py] [track_end()] "\
                    + f"[{rec['bkgNo']} not closed for {rec.get('user', None)}]")
    except ConnectionFailure:
        log("[oneline_update.py] [track_end()] "\
            + f"[DB Connection failure]")
        return False
    except BaseException as err:
        log("[oneline_update.py] [track_end()] "\
            + f"[{err.details}]")
        return False

# Helper fuction for main()
def conn_db(path, env):
    """Return connection and database objects."""
    with open(path, "r") as f:
        conf = json.load(f)
    conn = MongoClient(conf["DB_FRONTEND_URI"])
    db = conn[env]
    return conn, db

# ETL Pipelines
def regular_schedule_update(conn, db):
    """Update records schedule which require update for all users.
    Will be started on schedule by crontab."""
    records = records_to_update(conn, db)
    raw_data = extract_schedule_details(records)
    transformed_data = transform(raw_data)
    update(conn, db, transformed_data)
    arrived_records = arrived(conn, db)
    track_end(conn, db, arrived_records)
    del db
    conn.close()

def user_schedule_update(conn, db, user):
    """Update all records schedule for single user.
    Seacargos web app service."""
    records = records_to_update(conn, db, user)
    raw_data = extract_schedule_details(records)
    transformed_data = transform(raw_data)
    update(conn, db, transformed_data)
    arrived_records = arrived(conn, db, user)
    track_end(conn, db, arrived_records)

def record_schedule_update(conn, db, user, bkg_number):
    """Update one record schedule for single user."""
    records = records_to_update(conn, db, user, bkg_number)
    raw_data = extract_schedule_details(records)
    transformed_data = transform(raw_data)
    update(conn, db, transformed_data, regular_update=False)

if __name__ == "__main__":
    """Main function."""
    env = os.environ.get("FLASK_ENV", "Not set")
    dev_path = "../../instance/dev_config.json"
    prod_path = "../../instance/prod_config.json"
    if env == "development":
        if os.path.exists(dev_path):
            conn, db = conn_db(dev_path, env)
        else:
            # Add log
            sys.exit()
    else:
        if os.path.exists(prod_path):
            conn, db = conn_db(prod_path, env)
        else:
            # Add log
            sys.exit()
    sys.exit(regular_schedule_update(conn, db))