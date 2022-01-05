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
from time import strftime, gmtime

bp = Blueprint('dashboard', __name__)

def user_login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('home'))
        elif g.user['role'] != 'user':
            abort(403, 'You are note authorized to view this page.')
        return view(**kwargs)
    return wrapped_view

@bp.before_app_request
def load_logged_in_user():
    """Loads logged in user from session to g."""
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        db = db_conn()[g.db_name]
        g.user = db.users.find_one({'_id': ObjectId(user_id)})

@bp.route('/dashboard', methods=('GET', 'POST'))
@user_login_required
def dashboard():
    """Home dashboard view function."""
    conn = db_conn()
    db = conn[g.db_name]
    content = {"table": "x"}
    
    # POST request code
    if request.method == 'POST':
        user_input = request.form["booking"]
        query = validate_user_input(user_input)
        #result = check_db_records(query, g.conn, db)
        if check_db_records(query, conn, db):
            content.update(pipeline(query, conn, db))
    
    # GET request code
    content.update(tracking_status_content(conn, db))
    tracking_data = db_tracking_data(g.user["name"], conn, db)
    table_data = schedule_table_data(tracking_data)
    content.update(table_data)

    return render_template('dashboard/dashboard.html', content=content)

# User input validation helper functions
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
            "name": g.user["name"], "trackEnd": None
            }
    else:
        flash(f"Incorrect booking or container number {user_input}")
        # Add logger record
        return False

def check_db_records(query, conn, db):
    """Use query argument to count documents in database
    shipments and tracking collections. Return True if count is 0
    in both collections."""
    if not query:
        #log("[oneline.py] [check_db_records()]"\
          #  + f" [Wrong query {query}]")
        return False
    try:
        conn.admin.command("ping")
        shipments = db.shipments.count_documents(query)
        tracking = db.tracking.count_documents(query)
        if shipments == 0 and tracking == 0:
            return True
        else:
            #log("[oneline.py] [check_db_records()]"\
            #    + f" [Record already exists for {query}]")
            #item = query.pop("bkgNo", None)
            if "bkgNo" in query:
                flash(f"Item {query['bkgNo']} already exists in tracking database.")
            else:
                flash(f"Item {query['cntrNo']} already exists in tracking database.")
            return False
    except ConnectionFailure:
        #log("[oneline.py] [check_db_records()]"\
        #    + f" [DB Connection failure for {query}]")
        flash("Database connection error.")
        return False
    except BaseException as err:
        #log("[oneline.py] [check_db_records()]"\
        #    + f" [{err.details} for {query}]")
        flash("Unexpected error.")
        return False

# DB content query helper functions
def tracking_status_content(conn, db):
    """Get tracking content from database."""
    try:
        conn.admin.command("ping")
        active = db.tracking.count_documents(
            {"user": g.user["name"], "trackEnd": None}
            )
        arrived = db.tracking.count_documents(
            {"user": g.user["name"], "trackEnd": {"$ne": None}}
            )
        total = db.shipments.count_documents({"user": g.user["name"]})
        content = {"active": active, "arrived": arrived, "total": total}
        return content
    except ConnectionFailure:
        #log("[oneline.py] [check_db_records()]"\
        #    + f" [DB Connection failure for {query}]")
        return {"tracking": "Database connection failure."}
    except BaseException as err:
        #log("[oneline.py] [check_db_records()]"\
        #    + f" [{err.details} for {query}]")
        return {"tracking": "Unexpected error."}

def db_tracking_data(user, conn, db):
    """Get shipments that did not reach destination from
    tracking collection."""
    if not user:
        #log("[oneline.py] [check_db_records()]"\
          #  + f" [Wrong query {query}]")
        return False
    try:
        conn.admin.command("ping")
        tracking_cursor = db.tracking.aggregate(
            [{"$match": {"user": user, "trackEnd": None}},
             {"$sort": {"departureDate": 1}}]
        )
        return json.loads(dumps(tracking_cursor))
    except ConnectionFailure:
        #log("[oneline.py] [check_db_records()]"\
        #    + f" [DB Connection failure for {query}]")
        return False
    except BaseException as err:
        #log("[oneline.py] [check_db_records()]"\
        #    + f" [{err.details} for {query}]")
        #print(err)
        return False

def schedule_table_data(records):
    """Prepare tracking shipments content."""
    def to_date(microsec):
        f_str = "%d-%m-%Y %H:%M"
        return strftime(f_str, gmtime(int(microsec) / 1000))
    table_data = {"table": []}
    for r in records:
        #departure = None
        #arrival = None
        #for s in r["schedule"]:
            #if s["event"].find("Departure from Port of Loading") > -1:
                #departure = to_time(s["eventDate"]["$date"])
            #if s["event"].find("Arrival at Port of Discharging") > -1:
                #arrival = to_time(s["eventDate"]["$date"])
    
        table_data["table"].append(
            {"booking": r["bkgNo"], "container": r["cntrNo"], "type": r["cntrType"],
             "from": {
                 "location": r["outboundTerminal"].split("|")[0],
                 "terminal": r["outboundTerminal"].split("|")[-1]
             },
             "departure": to_date(r["departureDate"]["$date"]),
             "to": {
                 "location": r["inboundTerminal"].split("|")[0],
                 "terminal": r["inboundTerminal"].split("|")[-1]
             },
             "arrival": to_date(r["arrivalDate"]["$date"])
            }
        )
    return table_data    