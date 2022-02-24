# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from flask import Blueprint
from flask import flash
from flask import g
from flask import session
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for


from bson.objectid import ObjectId
import functools
from werkzeug.exceptions import abort
from werkzeug.security import check_password_hash, generate_password_hash
from seacargos.db import db_conn
import os

bp = Blueprint('admin', __name__)

@bp.before_app_request
def load_logged_in_user():
    """Loads logged in user from session to g."""
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        db = db_conn()[g.db_name]
        g.user = db.users.find_one({"_id": ObjectId(user_id)})

def admin_login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('home.home'))
        elif g.user['role'] != 'admin':
            abort(403, 'You are not authorized to view this page.')
        return view(**kwargs)
    return wrapped_view

@bp.route("/admin")
@admin_login_required
def admin():
    """Admin panel page."""
    db = db_conn()[g.db_name]
    content = {}
    content["users"] = users(db)
    content["db"] = database(db)
    content["etl_log"] = etl_logs()
    #flash("test message")
    return render_template('admin/admin.html', content=content)

@bp.route("/admin/add-user", methods=("GET", "POST"))
@admin_login_required
def add_user():
    """Add new user form page."""
    db = db_conn()[g.db_name]
    content = {"options": ["admin", "user"]}
    # POST method
    if request.method == "POST":
        name = request.form["user-name"]
        role = request.form["role"]
        pwd = request.form["pwd"]
        pwd_repeat = request.form["pwd-repeat"]
        if db.users.find_one({"name": name}):
            flash(f"User name '{name}' already exists")
        elif pwd != pwd_repeat:
            flash("Passwords does not match")
        else:
            pwd_hash = generate_password_hash(pwd)
            db.users.insert_one(
                {"name": name, "role": role, "password": pwd_hash}
            )
            flash("New user successfully added to database")


    return render_template("admin/add-user.html", content=content)

def size(bytes):
    """Accepts size in bytes as integer and returns size as string
    with Kb, Mb or Gb abbr."""
    if bytes < 1024:
        return str(bytes) + "bytes"
    elif bytes < 1024**2:
        return str(round(bytes / 1024, 1)) + " Kb"
    elif bytes < 1024**3:
        return str(round(bytes / 1024**2, 1)) + " Mb"
    else:
        return str(round(bytes / 1024**3, 1)) + " Gb"

# Helper functions
def users(db):
    """Prepare and return user stats."""
    data = {}
    data["admin"] = db.users.count_documents({"role": "admin"})
    data["user"] = db.users.count_documents({"role": "user"})
    return data

def database(db):
    """Prepare and return database stats."""
    stats = {"collections": []}
    db_stats = db.command("dbstats")
    collections = db.list_collection_names()
    stats["storage_size"] = size(db_stats["storageSize"])
    stats["objects"] = db_stats["objects"]
    for coll in collections:
        data = {"name": coll}
        coll_stats = db.command("collstats", coll)
        data["storage_size"] = size(coll_stats["storageSize"])
        data["objects"] = coll_stats["count"]
        stats["collections"].append(data)
    return stats

def etl_logs():
    """Prepare and return etl log stats."""
    stats = {}
    if os.path.exists("etl.log"):
        with open("etl.log", "r") as f:
            logs = len(f.readlines())
    else:
        with open("etl.log", "a") as f:
            logs = 0
    stats["logs"] = logs
    stats["size"] = size(os.path.getsize("etl.log"))
    return stats
