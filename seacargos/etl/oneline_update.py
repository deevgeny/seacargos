"""ETL pipeline for updating ONE container shipping records in database.

This module defines ETL (Extract Transform Load) pipelines to update ONE
container shippings in database:
- regular_schedule_update(): ETL pipline to update all records in database.
- user_schedule_update(): ETL pipeline to update all records in databse which
belong to a specific user.
- record_schedule_update(): ETL pipeline to update specific record in database.
Other functions in this module are helper functions which make hard job of
data extraction, transformation and loading to database."""

import json
import logging
import os
import sys
from datetime import datetime
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from typing import List, Optional

import requests
from bson.json_util import dumps
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure

logger = logging.getLogger('ONE ETL UPDATE')

URL = os.getenv("ONE_URL")
if not URL:
    logger.error("ONE_URL envoronment variable is not available.")


def records_to_update(conn: MongoClient, db: Database,
                      user: Optional[str] = None,
                      bkg_number: Optional[str] = None) -> Optional[dict]:
    """Prepare database records which require update.

    Supports three options:
    - Update all user records: user='username'
    - Update one user record: user='username' and bkg_number='number'
    - Bulk update (all users records): user=None and bkg_number=None
    """
    # Prepare query
    project = {"user": 1, "bkgNo": 1, "copNo": 1, "_id": 0}
    query = {"trackEnd": None}
    if user and bkg_number:
        query["user"] = user
        query["bkgNo"] = bkg_number
    elif user:
        query["user"] = user
    else:
        now = datetime.now().replace(microsecond=0)
        query["schedule"] = {
            "$elemMatch": {"status": "E", "eventDate": {"$lte": now}}
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
            logger.info(f"Nothing to update for query: {query}.")
            return
    except ConnectionFailure:
        logger.error(f"Database connection failure for query: {query}.")
        return
    except BaseException as err:
        logger.error(f"Unexpected error for query {query}: {err}.")
        return


def extract_schedule_details(records: Optional[dict]) -> Optional[dict]:
    """Extract schedule data for ONE container records.

    Make GET request to extract container schedule data for update.
    """
    if not records:
        return
    # Extract data
    for rec in records:
        # Prepare request payload
        payload = {
            '_search': 'false', 'f_cmd': '125', 'cntr_no': "",
            'bkg_no': rec["bkgNo"], 'cop_no': rec["copNo"]
        }
        # Make request
        r = requests.get(URL, params=payload)
        if r.status_code != HTTPStatus.OK:
            logger.warning(
                ("ONE site is unavailable with response status code: "
                 f"{r.status_code}.")
            )
            return
        data = r.json()
        # Update schedule data
        if "list" in data:
            schedule_data = data["list"]
            schedule_data[0].pop("hashColumns", None)
            rec["schedule"] = schedule_data
        else:
            logger.warning(
                f"Schedule data is missing for record: {rec['bkgNo']}"
            )
            rec["schedule"] = None
    return records


def str_to_date(string: str) -> datetime:
    """Convert string to date."""
    if len(string) == 16:
        return datetime.strptime(string, "%Y-%m-%d %H:%M")
    return datetime.fromtimestamp(0)


def transform(records: Optional[dict]) -> Optional[dict]:
    """Transforms ONE container records raw data.

    Prepare raw data extracted from ONE shipper for updating in database.
    """
    # Check input
    if not records:
        return

    # Transform raw data
    schedule_keys = ["no", "statusNm", "placeNm", "yardNm",
                     "eventDt", "actTpCd", "actTpCd", "vslEngNm",
                     "lloydNo"]
    for rec in records:
        # Check required schedule keys exist in raw data
        if not set(schedule_keys).issubset(set(rec["schedule"][0])):
            logger.warning(
                ("Required schedule keys are missing in response data for "
                 f"database record {rec['bkgNo']}.")
            )
            rec["schedule"] = None
            continue
        # Transform record raw data
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
            # Update arrival/departure dates and terminals
            if i["statusNm"].find("Departure from Port of Loading") > -1:
                rec["departureDate"] = str_to_date(i["eventDt"])
                rec["outboundTerminal"] = f"{i['placeNm']} | {i['yardNm']}"
            if i["statusNm"].find("Arrival at Port of Discharging") > -1:
                rec["arrivalDate"] = str_to_date(i["eventDt"])
                rec["inboundTerminal"] = f"{i['placeNm']} | {i['yardNm']}"
            rec["schedule"] = transformed_schedule
    return records


def update(conn: MongoClient, db: Database, records: Optional[dict],
           regular_update: bool = True) -> None:
    """Update records in database."""
    if not records:
        return
    query = {"bkgNo": None, "trackEnd": None}
    update = {"$set": {"schedule": None,
                       "recordUpdate": datetime.now().replace(microsecond=0)}
              }
    if regular_update:
        update["$set"]["regularUpdate"] = update["$set"]["recordUpdate"]
    update_keys = ["departureDate", "outboundTerminal", "arrivalDate",
                   "inboundTerminal"]
    try:
        conn.admin.command("ping")
        for rec in records:
            if not rec["schedule"]:
                logger.warning(
                    (f"Record with booking number {rec['bkgNo']} has not been "
                     "updated, schedule data is missing.")
                )
                continue
            query["bkgNo"] = rec["bkgNo"]
            update["$set"]["schedule"] = rec["schedule"]
            if "user" in rec:
                query["user"] = rec["user"]
            for key in update_keys:
                if key in rec:
                    update["$set"][key] = rec[key]
            cursor = db.tracking.update_one(query, update)
            if not cursor.raw_result["updatedExisting"]:
                logger.info(
                    (f"Update status for record {rec['bkgNo']} and "
                     f"user {rec.get('user', None)}: {cursor.raw_result}")
                )
    except ConnectionFailure:
        logger.error("Database connection failure for update operation.")
    except BaseException as err:
        logger.error(f"Unexpected error during update operation: {err}")


def arrived(conn: MongoClient, db: Database,
            user: Optional[str] = None) -> Optional[dict]:
    """Find containers in database which arrived to destination.

    Supports two options:
    - Find user containers: user='username'
    - Find all containers: user=None
    """
    query = {"trackEnd": None}
    if user:
        query["user"] = user
    try:
        conn.admin.command("ping")
        cur = db.tracking.aggregate([
            {"$match": query},
            {"$addFields": {"last": {"$last": "$schedule"}}},
            {"$match": {"last.status": "A"}},
            {"$project": {"bkgNo": 1, "_id": 0}}
        ])
        records = json.loads(dumps(cur))
        if len(records) > 0:
            return records
    except ConnectionFailure:
        logger.error("Database connection failure.")
    except BaseException as err:
        logger.error(f"Unexpected error during database query: {err}")


def track_end(conn: MongoClient, db: Database,
              records: Optional[List[dict]]) -> None:
    """Update trackEnd field in database.

    Set trackEnd field to current date and time for records passed in
    a list: records=[{record1}, {record2}...].
    """
    if not records:
        return
    try:
        conn.admin.command("ping")
        query = {"bkgNo": None, "trackEnd": None}
        for rec in records:
            query["bkgNo"] = rec["bkgNo"]
            cursor = db.tracking.update_one(
                query,
                {"$set": {"trackEnd": datetime.now().replace(microsecond=0)}},
            )
            if not cursor.raw_result["updatedExisting"]:
                logger.error(
                    (f"Failed to set trackEnd for record {rec['bkgNo']} "
                     f"{cursor.raw_result}")
                )
    except ConnectionFailure:
        logger.error("Database connection failure.")
    except BaseException as err:
        logger.error(f"Unexpected error during database query: {err}")


def regular_schedule_update(conn, db) -> None:
    """Update all ONE shipping records schedules in database.

    ETL steps:
    - Query database for records which need to be updated.
    - Extract schedule data for the selected records.
    - Transform extracted data.
    - Update the records with new data.
    - Check records which arrived to destination and set 'trackEnd' field
    equal to current date and time.
    """
    records = records_to_update(conn, db)
    raw_data = extract_schedule_details(records)
    transformed_data = transform(raw_data)
    update(conn, db, transformed_data)
    arrived_records = arrived(conn, db)
    track_end(conn, db, arrived_records)


def user_schedule_update(conn: MongoClient, db: Database,
                         user: str) -> None:
    """Update all ONE shipping records schedules for a single user.

    ETL steps:
    - Query database for records which need to be updated.
    - Extract schedule data for the selected records.
    - Transform extracted data.
    - Update the records with new data.
    - Check records which arrived to destination and set 'trackEnd' field
    equal to current date and time.
    """
    records = records_to_update(conn, db, user)
    raw_data = extract_schedule_details(records)
    transformed_data = transform(raw_data)
    update(conn, db, transformed_data)
    arrived_records = arrived(conn, db, user)
    track_end(conn, db, arrived_records)


def record_schedule_update(conn: MongoClient, db: Database,
                           user: Optional[str],
                           bkg_number: Optional[str]) -> None:
    """Update one record schedule for single user.

    ETL steps:
    - Query database for a record which need to be updated.
    - Extract schedule data for the selected record.
    - Transform extracted data.
    - Update the record with new data.
    """
    records = records_to_update(conn, db, user, bkg_number)
    raw_data = extract_schedule_details(records)
    transformed_data = transform(raw_data)
    update(conn, db, transformed_data, regular_update=False)


def main() -> int:
    """Main module function for ONE shipments regular update.

    Can be envoked periodically by schedulers like crontab.
    """
    update_logger = logging.getLogger("ONE ETL REGULAR UPDATE")
    update_logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        '../logs/one_regular_update.log', maxBytes=5000000, backupCount=5
    )
    formatter = logging.Formatter(
        ('%(asctime)s - %(levelname)s - %(name)s - '
         '%(filename)s in %(funcName)s:%(lineno)s - %(message)s')
    )
    handler.setFormatter(formatter)
    update_logger.addHandler(handler)
    update_logger.info("Start regular schedule update.")
    URL = os.getenv("FLASK_DB_FRONTEND_URI")
    DB_NAME = os.getenv("FLASK_DB_NAME")
    if not URL and not DB_NAME:
        update_logger.error(
            "Environment variables for database connection are not available"
        )
        return 1
    conn = MongoClient(URL)
    db = conn[DB_NAME]
    regular_schedule_update(conn, db)
    del db
    conn.close()
    update_logger.info("Regular schedule update completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
