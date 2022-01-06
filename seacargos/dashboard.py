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
    content = {}
    
    # POST request
    if request.method == 'POST':
        user_input = request.form["booking"]
        query = validate_user_input(user_input)
        #result = check_db_records(query, g.conn, db)
        if check_db_records(query, conn, db):
            content.update(pipeline(query, conn, db))
    
    # GET request
    content.update(tracking_status_content(conn, db))
    tracking_data = db_tracking_data(g.user["name"], conn, db)
    table_data = schedule_table_data(tracking_data)
    content.update(table_data)

    return render_template('dashboard/dashboard.html', content=content)

def ping(func):
    """Catch database CRUD ops exceptions """
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

@ping
def check_db_records(query, conn, db):
    """Use query argument to count documents in database
    shipments and tracking collections. Return True if count is 0
    in both collections."""
    if not query:
        #log("[oneline.py] [check_db_records()]"\
          #  + f" [Wrong query {query}]")
        return False
    tracking = db.tracking.count_documents(query)
    if tracking == 0:
        return True
    else:
        #log("[oneline.py] [check_db_records()]"\
        #    + f" [Record already exists for {query}]")
        if "bkgNo" in query:
            flash(f"Item {query['bkgNo']} already exists in tracking database.")
        else:
            flash(f"Item {query['cntrNo']} already exists in tracking database.")
        return False

# DB content query helper functions
@ping
def tracking_status_content(conn, db):
    """Get tracking content from database."""
    active = db.tracking.count_documents(
        {"user": g.user["name"], "trackEnd": None}
        )
    arrived = db.tracking.count_documents(
        {"user": g.user["name"], "trackEnd": {"$ne": None}}
        )
    total = db.shipments.count_documents({"user": g.user["name"]})
    content = {"active": active, "arrived": arrived, "total": total}
    return content

@ping
def db_tracking_data(user, conn, db):
    """Get shipments that did not reach destination from
    tracking collection."""
    if not user:
        #log("[oneline.py] [check_db_records()]"\
          #  + f" [Wrong query {query}]")
        return False
    tracking_cursor = db.tracking.aggregate(
        [{"$match": {"user": user, "trackEnd": None}},
         {"$sort": {"departureDate": -1}},
         {"$project": {"schedule": 0}}]
    )
    return json.loads(dumps(tracking_cursor))

def schedule_table_data(records):
    """Prepare tracking shipments content."""
    def to_date_str(microsec):
        """Transform microseconds string into date string."""
        f_str = "%d-%m-%Y %H:%M"
        return strftime(f_str, gmtime(int(microsec) / 1000))

    table_data = {"table": []}
    for r in records:
        table_data["table"].append(
            {"booking": r["bkgNo"], "container": r["cntrNo"],
             "type": r["cntrType"],
             "from": {
                 "location": r["outboundTerminal"].split("|")[0],
                 "terminal": r["outboundTerminal"].split("|")[-1]
                },
             "departure": to_date_str(r["departureDate"]["$date"]),
             "to": {
                 "location": r["inboundTerminal"].split("|")[0],
                 "terminal": r["inboundTerminal"].split("|")[-1]
                },
             "arrival": to_date_str(r["arrivalDate"]["$date"])
            }
        )
    return table_data    