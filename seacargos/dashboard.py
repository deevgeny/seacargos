# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from flask import (
    Blueprint, flash, g, redirect, render_template, session, request, url_for
)
from werkzeug.exceptions import abort
from werkzeug.security import check_password_hash, generate_password_hash
from markupsafe import escape

import functools
import json
from datetime import datetime as dt
from bson.json_util import dumps
from bson.objectid import ObjectId
from seacargos.db import db_conn
from pymongo.errors import ConnectionFailure

from seacargos.etl.oneline import etl_one
from seacargos.etl.oneline_update import user_schedule_update
from seacargos.etl.oneline_update import record_schedule_update

bp = Blueprint("dashboard", __name__)

def log(message):
    """Log function to log errors (debug version)."""
    timestamp = dt.strftime(dt.now(), "%Y-%m-%d %H:%M:%S")
    with open("etl.log", "a") as f:
        f.write("\n" + timestamp + " " + message)

def user_login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("home"))
        elif g.user["role"] != "user":
            abort(403, "You are note authorized to view this page.")
        return view(**kwargs)
    return wrapped_view

@bp.before_app_request
def load_logged_in_user():
    """Loads logged in user from session to g."""
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        db = db_conn()[g.db_name]
        g.user = db.users.find_one({"_id": ObjectId(user_id)})

@bp.route("/dashboard", methods=("GET", "POST"))
@user_login_required
def dashboard():
    """Home dashboard view function."""
    conn = db_conn()
    db = conn[g.db_name]
    content = {}
    
    # POST request
    if request.method == "POST":
        # Check booking number input
        user_input = request.form["booking"]
        query = validate_user_input(user_input)
        # Check refId input
        if len(request.form["refId"]) > 0:
            query["refId"] = request.form["refId"]
        else:
            query["refId"] = "-"
        # Check requested ETA input
        if len(request.form["requestedETA"]) > 0:
            query["requestedETA"] = request.form["requestedETA"]
        else:
            query["requestedETA"] = "-"
        # Check query vs db records
        if check_db_records(query, db):
            content.update(etl_one(query, conn, db))
    
    # GET request
    content.update(tracking_summary(db, g.user["name"]))
    cursor = db_tracking_data(g.user["name"], db)
    table_data = schedule_table_data(cursor)
    content.update(table_data)

    return render_template("dashboard/dashboard.html", content=content)

@bp.route("/dashboard/<bkg_number>")
@user_login_required
def details(bkg_number):
    """View to display shipment details."""
    db = db_conn()[g.db_name]
    content = {}
    record = db_get_record(db, bkg_number, g.user["name"])
    if record:
        content["details"] = prepare_record_details(record)
        content["bkg_number"] = bkg_number
        content["record_update"] = \
            dt.strftime(record["recordUpdate"], "%d-%m-%Y %H:%M")
    else:
        flash(f"Record {bkg_number} not found in database.")
    return render_template("/dashboard/details.html", content=content)

@bp.route("/dashboard/update")
@user_login_required
def update():
    """Update user shipments schedules for all records."""
    conn = db_conn()
    db = conn[g.db_name]
    user = g.user["name"]
    user_schedule_update(conn, db, user)

    return redirect(url_for("dashboard"))

@bp.route("/dashboard/update/<bkg_number>")
@user_login_required
def update_record(bkg_number):
    """Update user shipment schedule for one record."""
    conn = db_conn()
    db = conn[g.db_name]
    user = g.user["name"]
    record_schedule_update(conn, db, user, bkg_number)

    return redirect(url_for("dashboard.details", bkg_number=bkg_number))

# Helper functions
def ping(func):
    """Catch database CRUD ops exceptions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionFailure as e:
            #log(f"[dashboard.py] [{func.__name__}]"\
            #    + f" [DB Connection failure for args {args}]")
            return False
        except BaseException as e:
            #log(f"[dashboard.py] [{func.__name__}]"\
            #    + f" [Base Exception: {e} for args: {args}]")
            return False
    return wrapper

def validate_user_input(user_input):
    """Validate user booking or container input.
    Return MongoDB query."""
    if len(user_input) == 12 and user_input[0:4].isalpha():
        return {
            "bkgNo": user_input.upper(), "line": "ONE",
            "user": g.user["name"], "trackEnd": None
            }
    elif len(user_input) == 11:
        return {
            "cntrNo": user_input.upper(), "line": "ONE",
            "user": g.user["name"], "trackEnd": None
            }
    else:
        flash(f"Incorrect booking or container number {user_input}")
        # Add logger record
        return False

@ping
def check_db_records(query, db):
    """Use query argument to count documents in database
    shipments and tracking collections. Return True if count is 0
    in both collections."""
    if not query:
        #log("[oneline.py] [check_db_records()]"\
          #  + f" [Wrong query {query}]")
        return False
    count = db.tracking.count_documents(query)
    if count == 0:
        return True
    else:
        #log("[oneline.py] [check_db_records()]"\
        #    + f" [Record already exists for {query}]")
        if "bkgNo" in query:
            flash(f"Item {query['bkgNo']} already exists in tracking database.")
        else:
            flash(f"Item {query['cntrNo']} already exists in tracking database.")
        return False

@ping
def tracking_summary(db, user):
    """Get tracking summary from database."""
    active = db.tracking.count_documents(
        {"user": user, "trackEnd": None}
        )
    arrived = db.tracking.count_documents(
        {"user": user, "trackEnd": {"$ne": None}}
        )
    total = db.tracking.count_documents({"user": user})
    last_update = db.tracking.aggregate(
        [{"$match": {"user": user, "trackEnd": None}},
         {"$sort": {"regularUpdate": -1}},
         {"$limit": 1},
         {"$project": {"regularUpdate": 1, "_id": 0}}]
    )

    if last_update._has_next():
        format_string = "%d-%m-%Y %H:%M"
        record = last_update.next()
        date = record["regularUpdate"].strftime(format_string)
    else:
        date = "-"

    summary = {"active": active, "arrived": arrived,
               "total": total, "updated_on": date}
    return summary

@ping
def db_tracking_data(user, db):
    """Get shipments that did not reach destination from
    tracking collection."""
    cursor = db.tracking.aggregate(
        [{"$match": {"user": user, "trackEnd": None}},
         {"$sort": {"departureDate": -1}},
         {"$project": {"_id": 0, "schedule": 0, "initSchedule": 0}}]
    )
    return cursor

def schedule_table_data(cursor):
    """Prepare schedule data for schedule table."""
    format_string = "%d-%m-%Y %H:%M"
    table_data = {"table": []}
    for c in cursor:
        # Check requestedETA and convert
        eta_delay = "-"
        if isinstance(c["requestedETA"], dt):
            eta_delay = (c["arrivalDate"] - c["requestedETA"]).days
            c["requestedETA"] = c["requestedETA"].strftime("%d-%m-%Y")

        # Construct and append table data row
        table_data["table"].append(
            {"refId": c["refId"],
             "booking": c["bkgNo"], "container": c["cntrNo"],
             "type": c["cntrType"],
             "from": {
                 "location": c["outboundTerminal"].split("|")[0],
                 "terminal": c["outboundTerminal"].split("|")[-1]
             },
             #"departure": dt.strftime(c["departureDate"], format_string),
             "departure": c["departureDate"].strftime(format_string),
             "to": {
                 "location": c["inboundTerminal"].split("|")[0],
                 "terminal": c["inboundTerminal"].split("|")[-1]
             },
             #"arrival": dt.strftime(c["arrivalDate"], format_string),
             "arrival": c["arrivalDate"].strftime(format_string),
             "totalDays": (c["arrivalDate"] - c["departureDate"]).days,
             "requestedETA": c["requestedETA"],
             "etaDelay": eta_delay
            }
        )
    return table_data

@ping
def db_get_record(db, bkg_number, user):
    """Get record from database tracking collection."""
    return db.tracking.find_one(
        {"bkgNo": bkg_number, "trackEnd": None, "user": user}
        )

def prepare_record_details(record):
    """Prepare tracking collection record details."""
    if record:
        format_string = "%d-%m-%Y %H:%M"
        details = []
        for i in zip(record["schedule"], record["initSchedule"]):
            row = {}
            row["event"] = i[0]["event"]
            row["placeName"] = i[0]["placeName"]
            row["yardName"] = i[0]["yardName"]
            row["plannedDate"] = dt.strftime(i[1]["eventDate"], format_string)
            row["actualDate"] = dt.strftime(i[0]["eventDate"], format_string)
            row["delta"] = (i[0]["eventDate"] - i[1]["eventDate"]).days
            row["status"] = i[0]["status"]
            details.append(row)
        return details