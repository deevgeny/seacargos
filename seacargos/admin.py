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
    content["users"] = users_stats(db)
    content["db"] = database_stats(db)
    content["etl_log"] = etl_log_stats()
    #flash("test message")
    return render_template('admin/admin.html', content=content)

@bp.route("/admin/add-user", methods=("GET", "POST"))
@admin_login_required
def add_user():
    """Add new user form page."""
    db = db_conn()[g.db_name]
    content = {"roles": ["admin", "user"]}
    # POST method
    if request.method == "POST":
        form_data = dict(request.form)
        if db.users.find_one({"name": form_data["user-name"]}):
            content["error"] =\
                f"User name {form_data['user-name']} already exists."
        elif form_data["pwd"] != form_data["pwd-repeat"]:
            content["error"] = "Passwords does not match."
        elif form_data["role"] == "":
            content["error"] = "Please select role."
        else:
            pwd_hash = generate_password_hash(form_data["pwd"])
            cur = db.users.insert_one(
                {"name": form_data['user-name'], "role": form_data["role"],
                "password": pwd_hash, "active": True}
            )
            if cur.acknowledged and cur.inserted_id:
                content["info"] = "New user successfully added to database."
            else:
                content["error"] = "Database write error."
                # Add log

    return render_template("admin/add_user.html", content=content)

@bp.route("/admin/edit-user", methods=("GET", "POST"))
@admin_login_required
def edit_user():
    """Edit new user form page."""
    db = db_conn()[g.db_name]
    content = {"roles": ["admin", "user"]}
    content["user_names"] = active_user_names_from_db(db)
    # POST method
    if request.method == "POST":
        query = {}
        change = {}
        form_data = dict(request.form)
        #content["form"] = form_data # Debug

        # Check user name
        if form_data["user-name"] != "":
            query["name"] = form_data["user-name"]
        
        # Check role
        if form_data["role"] != "":
            change["role"] = form_data["role"]

        # Check passwords
        if form_data["pwd"] != "" and form_data["pwd"] == form_data["pwd-repeat"]:
            change["password"] = generate_password_hash(form_data["pwd"])
        elif form_data["pwd"] != form_data["pwd-repeat"]:
            content["error"] = "Passwords does not match."
        
        # Check request and change data, and make update or send error message
        if len(query) == 1 and len(change) > 0:
            cur = db.users.update_one(query, {"$set": change})
            if cur.raw_result["updatedExisting"]:
                content["info"] = "User data successfully updated."
            else:
                content["error"] = "User data was not updated."
        elif len(query) == 0:
            content["error"] = "Please select user."
        elif len(change) == 0 and content.get("error", None) == None:
            content["error"] = "Edit fields have been not filled."

    return render_template("admin/edit_user.html", content=content)

@bp.route("/admin/delete-user", methods=("GET", "POST"))
@admin_login_required
def delete_user():
    """Edit new user form page."""
    db = db_conn()[g.db_name]
    content = {}
    content["user_names"] = active_user_names_from_db(db)
    # POST method
    if request.method == "POST":
        form_data = dict(request.form)
        if form_data["user-name"] != "":
            db.users.update(
                {"name": form_data["user-name"]},
                {"$set": {"active": False}}
                )
        else:
            content["error"] = "Please select user."

    return render_template("admin/delete_user.html", content=content)

def size(bytes):
    """Accepts size in bytes as integer and returns size as string
    with Kb, Mb or Gb abbr."""
    if bytes < 1024:
        return str(bytes) + " bytes"
    elif bytes < 1024**2:
        return str(round(bytes / 1024, 1)) + " Kb"
    elif bytes < 1024**3:
        return str(round(bytes / 1024**2, 1)) + " Mb"
    else:
        return str(round(bytes / 1024**3, 1)) + " Gb"

# Helper functions
# Admin
def users_stats(db):
    """Prepare and return user stats."""
    stats = {}
    stats["admin"] = db.users.count_documents({"role": "admin"})
    stats["user"] = db.users.count_documents({"role": "user"})
    return stats

# Admin
def database_stats(db):
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

# Admin
def etl_log_stats():
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

# Admin/edit-user and admin/delete-user
def active_user_names_from_db(db):
    """Returns all user names from database in list."""
    names = []
    cursor = db.users.find({"active": True}, {"_id": 0, "name": 1})
    for c in cursor:
        names.append(c["name"])
    return names
    