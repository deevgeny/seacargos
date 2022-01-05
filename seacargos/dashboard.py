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
    
    # POST request code
    if request.method == 'POST':
        user_input = request.form["booking"]
        query = validate_user_input(user_input)
        #result = check_db_records(query, g.conn, db)
        if check_db_records(query, conn, db):
            content.update(pipeline(query, conn, db))
    
    # GET request code
    content.update(tracking_content(conn, db))

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
            "cntrNo": user_input.upper(), "line": None,
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
            flash("This record already exists.")
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
def tracking_content(conn, db):
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