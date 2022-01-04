import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, session, request, url_for
)
from werkzeug.exceptions import abort
from werkzeug.security import check_password_hash, generate_password_hash
from seacargos.db import db_conn
from bson.objectid import ObjectId
from seacargos.etl.oneline import check_db_records

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
        db = db_conn()[g.db]
        g.user = db.users.find_one({'_id': ObjectId(user_id)})

@bp.route('/dashboard', methods=('GET', 'POST'))
@user_login_required
def dashboard():
    """Home dashboard view function."""
    if request.method == 'POST':
        user_input = request.form["booking"]
        valid_user_input = validate_user_input(user_input)
        query = prepare_db_query(valid_user_input)
        result = check_db_records(query, g.conn, g.conn[g.db])
        flash(f"User input: {user_input}")
        flash(f"Validated user input: {valid_user_input}")
        flash(f"Query: {query}")
        flash(f"check_db_records(): {result}")
        
    
    content = {}

    return render_template('dashboard/dashboard.html', content=content)

# Helper functions
def validate_user_input(user_input):
    """Validate user input."""
    if len(user_input) == 12 and user_input[0:4].isalpha():
        return {"bkgNo": user_input.upper(), "line": "ONE"}
    elif len(user_input) == 11:
        return {"cntrNo": user_input.upper(), "line": None}
    else:
        flash(f"Incorrect booking or container number {user_input}")
        # Add logger record
        return False

def prepare_db_query(valid_user_input):
    """Prepare MongoDB query based on valid user input."""
    if not valid_user_input:
        return False
    valid_user_input["user"] = g.user["name"]
    return valid_user_input