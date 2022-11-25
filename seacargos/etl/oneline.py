"""ETL pipeline for creating ONE container shipping records in database.

This module defines ETL (Extract Transform Load) pipeline for ONE
container shippings. Main ETL logic function is etl_one(). Other functions
in this module are helper functions which make hard job of data extraction,
transformation and loading to database."""

import logging
import os
import time
from datetime import datetime
from http import HTTPStatus
from typing import Optional

import requests
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure

logger = logging.getLogger("ONE ETL")

URL = os.getenv("ONE_URL")
if not URL:
    logger.error("ONE_URL envoronment variable is not available.")


def extract_container_data(query: dict) -> tuple:
    """Extract container data for ONE containers.

    Make GET request and extract container data from response.
    """
    # Prepare payload and make get request
    payload = {
        "_search": "false", "nd": str(time.time_ns())[:-6],
        "rows": "10000", "page": "1", "sidx": "",
        "sord": "asc", "f_cmd": "121", "search_type": "A",
        "search_name": (query.get("bkgNo", None)
                            or query.get("cntrNo", None)), "cust_cd": "",
    }
    r = requests.get(URL, params=payload)
    if r.status_code != HTTPStatus.OK:
        logger.warning(
            ("ONE site is unavailable with response status code: "
             f"{r.status_code}.")
        )
        return query, None
    data = r.json()
    # Extract data from response
    if "list" in data:
        container_data = data["list"][0]
        container_data.pop("hashColumns", None)
        return query, container_data

    logger.warning(f"Container data is missing for query: {query}.")
    return query, None


def extract_schedule_data(query: dict,
                          container_data: Optional[dict]) -> Optional[dict]:
    """Extract schedule data for ONE container.

    Make GET request and extract schedule data from response.
    """
    if not container_data:
        logger.warning("Container data is missing.")
        return
    payload = {
        "_search": "false", "f_cmd": "125",
        "cntr_no": container_data["cntrNo"],
        "bkg_no": "", "cop_no": container_data["copNo"]
    }
    r = requests.get(URL, params=payload)
    if r.status_code != HTTPStatus.OK:
        logger.warning(
            f"ONE site is unavailable, response status code: {r.status_code}."
        )
        return
    data = r.json()
    if "list" in data:
        schedule_data = data["list"]
        schedule_data[0].pop("hashColumns", None)
        return {"container_data": container_data,
                "schedule_data": schedule_data,
                "query": query}

    logger.warning(f"Schedule data is missing for query: {query}.")


def transform_data(data: Optional[dict]) -> Optional[dict]:
    """Transform ONE container raw response data.

    Prepare raw data extracted from ONE shipper for loading to database.
    """
    if not data:
        logger.warning("Raw data is missing.")
        return

    # Check required contnainer keys exist in raw data
    cntr_keys = ["cntrNo", "cntrTpszNm", "copNo", "blNo"]
    if not set(cntr_keys).issubset(set(data["container_data"])):
        logger.warning(
            ("Required container keys are missing in response data for query: "
             f"{data['query']}.")
        )
        return

    # Check required schedule keys exist in raw data
    schedule_keys = ["no", "statusNm", "placeNm", "yardNm", "eventDt",
                     "actTpCd", "actTpCd", "vslEngNm", "lloydNo"]
    if not set(schedule_keys).issubset(set(data["schedule_data"][0])):
        logger.warning(
            ("Required container keys are missing in response data for query: "
             f"{data['query']}.")
        )
        return

    def to_date_obj(string: str) -> datetime:
        """Transform string date to datetime object."""
        if len(string) == 0:
            return ''
        f_str = "%Y-%m-%d %H:%M"
        return datetime.strptime(string, f_str)

    # Transform container data
    if len(data["query"]["requestedETA"]) > 1:
        data["query"]["requestedETA"] = datetime.strptime(
            data["query"]["requestedETA"], "%Y-%m-%d"
        )
    timestamp = datetime.now().replace(microsecond=0)
    result = {
        "cntrNo": data["container_data"]["cntrNo"],
        "cntrType": data["container_data"]["cntrTpszNm"],
        "copNo": data["container_data"]["copNo"],
        "bkgNo": data["container_data"]["bkgNo"],
        "blNo": data["container_data"]["blNo"],
        "user": data["query"]["user"], "line": data["query"]["line"],
        "refId": data["query"]["refId"],
        "requestedETA": data["query"]["requestedETA"],
        "trackStart": timestamp,
        "regularUpdate": timestamp,
        "recordUpdate": timestamp,
        "trackEnd": None, "outboundTerminal": "", "departureDate": "",
        "inboundTerminal": "", "arrivalDate": "", "vesselName": None,
        "location": None, "schedule": None,
    }

    # Transform schedule data
    schedule = []
    for i in data["schedule_data"]:
        # Add schedule item point
        schedule.append({
            "no": int(i["no"]), "event": i["statusNm"],
            "placeName": i["placeNm"], "yardName": i["yardNm"],
            "eventDate": to_date_obj(i["eventDt"]), "status": i["actTpCd"],
            "vesselName": i["vslEngNm"], "imo": i["lloydNo"]
        })
        # Find & save outbound/inbound terminals & departure/arrival dates
        if i["statusNm"].find("Departure from Port of Loading") > -1:
            result["outboundTerminal"] = f"{i['placeNm']} | {i['yardNm']}"
            result["departureDate"] = to_date_obj(i["eventDt"])
        if i["statusNm"].find("Arrival at Port of Discharging") > -1:
            result["inboundTerminal"] = f"{i['placeNm']} | {i['yardNm']}"
            result["arrivalDate"] = to_date_obj(i["eventDt"])
    result["schedule"] = schedule
    result["initSchedule"] = schedule
    return result


def load_data(data: Optional[dict], conn: MongoClient, db: Database) -> dict:
    """Loads data into mongo database.

    Loads data to mongo database tracking collection. Returns dictionary
    with status message for html template.
    """
    if not data:
        logger.warning("No data to load to database.")
        return {"etl_message": "Requested data is not availabe yet."}
    try:
        conn.admin.command("ping")
        cursor = db.tracking.insert_one(data)
        if cursor.acknowledged:
            return {"etl_message": "New record successfully added"}
        else:
            logger.error(
                (f"Requested data {data['bkgNo']} not loaded to tracking "
                 "collection.")
            )
            return {"etl_message": "Database write operation failure"}
    except ConnectionFailure:
        logger.error(
            f"Database connection failure for {data['bkgNo']} write operation."
        )
        return {"etl_message": "Database connection failure"}
    except BaseException as err:
        logger.error(
            f"Unexpected error for {data['bkgNo']} write operation: {err}."
        )
        return {"etl_message": "Unexpected error"}


def etl_one(query: dict, conn: MongoClient, db: Database) -> dict:
    """ETL pipeline for ONE container shippings."""
    _, container_data = extract_container_data(query)
    raw_data = extract_schedule_data(query, container_data)
    transformed_data = transform_data(raw_data)
    result = load_data(transformed_data, conn, db)
    return result
