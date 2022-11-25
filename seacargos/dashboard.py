import functools
import logging
from datetime import datetime as dt
from typing import Optional

from bson.objectid import ObjectId
from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymongo.command_cursor import CommandCursor
from pymongo.database import Database
from pymongo.errors import ConnectionFailure
from werkzeug.exceptions import abort

from db import db_conn
from etl.oneline import etl_one
from etl.oneline_update import record_schedule_update, user_schedule_update

bp = Blueprint("dashboard", __name__)
logger = logging.getLogger("WEB APP")


@bp.before_app_request
def load_logged_in_user():
    """Loads logged in user from session to g."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = db_conn()[g.db_name]
        g.user = db.users.find_one({"_id": ObjectId(user_id)})


def user_login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("home"))
        elif g.user["role"] != "user":
            abort(403, "You are not authorized to view this page.")
        return view(**kwargs)
    return wrapped_view


@bp.route("/dashboard", methods=("GET", "POST"))
@user_login_required
def dashboard():
    """Home dashboard view function."""
    conn = db_conn()
    db = conn[g.db_name]
    content = {}

    # POST request
    if request.method == "POST":
        # Validate booking number
        booking = request.form["booking"]
        query = validate_booking_number(booking)

        # Prevent records duplication in database
        if check_db_records(query, db):
            # Prepare default values
            query["refId"] = "-"
            query["requestedETA"] = "-"

            # Check refId input and update value
            if len(request.form["refId"]) > 0:
                query["refId"] = request.form["refId"]

            # Check requested ETA input and update value
            if request.form["requestedETA"].replace("/", "").isnumeric():
                query["requestedETA"] = request.form["requestedETA"]

            # Run ETL and update content
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
        content["record_update"] = dt.strftime(record["recordUpdate"],
                                               "%d-%m-%Y %H:%M")
    else:
        flash(f"Record {bkg_number} not found in database.")
        logger.warning(f"Record {bkg_number} not found in database.")
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


def ping(func):
    """Catch database CRUD ops exceptions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionFailure:
            logger.error("Database connection error.")
            return
        except BaseException as e:
            logger.error(f"Unexpected error {e.args}")
            return
    return wrapper


def validate_booking_number(user_input: str) -> Optional[dict]:
    """Validate user booking or container number input.
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
        return


@ping
def check_db_records(query: dict, db: Database) -> Optional[bool]:
    """Use query argument to count documents in database tracking collection.

    Returns True if count is 0."""
    if not query:
        return
    count = db.tracking.count_documents(query)
    if count == 0:
        return True
    else:
        if "bkgNo" in query:
            flash(
                f"Item {query['bkgNo']} already exists in tracking database."
            )
        else:
            flash(
                f"Item {query['cntrNo']} already exists in tracking database."
            )


@ping
def tracking_summary(db: Database, user: str) -> dict:
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
def db_tracking_data(user: str, db: Database) -> CommandCursor:
    """Get shipments that did not reach destination from
    tracking collection."""
    cursor = db.tracking.aggregate(
        [{"$match": {"user": user, "trackEnd": None}},
         {"$sort": {"departureDate": -1}},
         {"$project": {"_id": 0, "schedule": 0, "initSchedule": 0}}]
    )
    return cursor


def schedule_table_data(cursor: CommandCursor) -> dict:
    """Prepare schedule data for schedule table."""
    format_string = "%d-%m-%Y %H:%M"
    table_data = {"table": []}
    for c in cursor:
        # Check requestedETA and convert to string
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
                # "departure": dt.strftime(c["departureDate"], format_string),
                "departure": c["departureDate"].strftime(format_string),
                "to": {
                 "location": c["inboundTerminal"].split("|")[0],
                 "terminal": c["inboundTerminal"].split("|")[-1]
            },
                # "arrival": dt.strftime(c["arrivalDate"], format_string),
                "arrival": c["arrivalDate"].strftime(format_string),
                "totalDays": (c["arrivalDate"] - c["departureDate"]).days,
                "requestedETA": c["requestedETA"],
                "etaDelay": eta_delay
            }
        )
    return table_data


@ping
def db_get_record(db: Database, bkg_number: str, user: str) -> dict:
    """Get record from database tracking collection."""
    return db.tracking.find_one(
        {"bkgNo": bkg_number, "trackEnd": None, "user": user}
    )


def prepare_record_details(record: Optional[dict]) -> Optional[dict]:
    """Prepare tracking collection record details."""
    if not record:
        return
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
