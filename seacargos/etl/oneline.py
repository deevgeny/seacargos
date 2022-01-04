import requests
import time
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.json_util import dumps

URL = "https://ecomm.one-line.com/ecom/CUP_HOM_3301GS.do"

def log(message):
    """Log function to log errors."""
    timestamp = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
    with open("etl.log", "a") as f:
        f.write(timestamp + " " + message + "\n")

def check_db_records(query, conn, db):
    """Use query argument to count documents in database
    shipments and tracking collections. Return True if count is 0
    in both collections."""
    if not query:
        log("[oneline.py] [check_db_records()]"\
            + f" [Wrong query {query}]")
        return False
    query["trackEnd"] = None
    try:
        conn.admin.command("ping")
        shipments = db.shipments.count_documents(query)
        tracking = db.tracking.count_documents(query)
        if shipments == 0 and tracking == 0:
            return True
        else:
            log("[oneline.py] [check_db_records()]"\
                + f" [Record already exists for {query}]")
            return False
    except ConnectionFailure:
        log("[oneline.py] [check_db_records()]"\
            + f" [DB Connection failure for {query}]")
        return False
    except BaseException as err:
        log("[oneline.py] [check_db_records()]"\
            + f" [{err.details} for {query}]")
        return False

