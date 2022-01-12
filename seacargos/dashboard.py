import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, session, request, url_for
)
from werkzeug.exceptions import abort
from werkzeug.security import check_password_hash, generate_password_hash
from seacargos.db import db_conn
from bson.objectid import ObjectId
from seacargos.etl.oneline import pipeline
from pymongo.errors import ConnectionFailure
import json
from bson.json_util import dumps
from datetime import datetime as dt
from markupsafe import escape

bp = Blueprint("dashboard", __name__)

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
        user_input = request.form["booking"]
        query = validate_user_input(user_input)
        if check_db_records(query, db):
            content.update(pipeline(query, conn, db))
    
    # GET request
    content.update(tracking_summary(db))
    tracking_data = db_tracking_data(g.user["name"], db)
    table_data = schedule_table_data(tracking_data)
    content.update(table_data)

    return render_template("dashboard/dashboard.html", content=content)

@bp.route("/dashboard/<bkg_number>")
@user_login_required
def details(bkg_number):
    """View to display shipment details."""
    db = db_conn()[g.db_name]
    records = db.tracking.find(
        {"bkgNo": bkg_number, "trackEnd": None, "user": g.user["name"]}
        )
    content = {"table": json.loads(dumps(records))}
    return render_template("/dashboard/details.html", content=content)


# Helper functions
def ping(func):
    """Catch database CRUD ops exceptions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionFailure as e:
            #log(f"[oneline.py] [{func.__name__}]"\
            #    + f" [DB Connection failure for args {*args}]")
            return False
        except BaseException as e:
            #log(f"[oneline.py] [{func.__name__}]"\
            #    + f" [Base Exception {e} for args {*args}]")
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
def tracking_summary(db):
    """Get tracking summary from database."""
    active = db.tracking.count_documents(
        {"user": g.user["name"], "trackEnd": None}
        )
    arrived = db.tracking.count_documents(
        {"user": g.user["name"], "trackEnd": {"$ne": None}}
        )
    total = db.tracking.count_documents({"user": g.user["name"]})
    summary = {"active": active, "arrived": arrived, "total": total}
    return summary

@ping
def db_tracking_data(user, db):
    """Get shipments that did not reach destination from
    tracking collection."""
    #if not user: - deprication
    #    #log("[oneline.py] [check_db_records()]"\
          #  + f" [Wrong query {query}]")
    #    return False
    tracking_cursor = db.tracking.aggregate(
        [{"$match": {"user": user, "trackEnd": None}},
         {"$sort": {"departureDate": -1}},
         {"$project": {"_id": 0, "schedule": 0, "initSchedule": 0}}]
    )
    return json.loads(dumps(tracking_cursor))

def schedule_table_data(records):
    """Prepare schedule data for schedule table."""
    format_string = "%d-%m-%Y %H:%M"
    table_data = {"table": []}
    for r in records:
        # Transform UTC microseconds to local datetime object
        dep_dt = dt.fromtimestamp(r["departureDate"]["$date"] / 1000)
        arr_dt = dt.fromtimestamp(r["arrivalDate"]["$date"] / 1000)
        # Find total number of days of delivery
        total_days = (arr_dt - dep_dt).days
        # Construct and append table data row
        table_data["table"].append(
            {"booking": r["bkgNo"], "container": r["cntrNo"],
             "type": r["cntrType"],
             "from": {
                 "location": r["outboundTerminal"].split("|")[0],
                 "terminal": r["outboundTerminal"].split("|")[-1]
                },
             "departure": dt.strftime(dep_dt, format_string),
             "to": {
                 "location": r["inboundTerminal"].split("|")[0],
                 "terminal": r["inboundTerminal"].split("|")[-1]
                },
             "arrival": dt.strftime(arr_dt, format_string),
             "totalDays": total_days
            }
        )
    return table_data    