import functools
import json
import os

from bson.json_util import dumps
from bson.objectid import ObjectId
from flask import (
    Blueprint,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from forms import AddUserForm
from pymongo.database import Database
from werkzeug.exceptions import abort
from werkzeug.security import generate_password_hash

from db import db_conn

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
            return redirect(url_for("home.home"))
        elif g.user['role'] != "admin":
            abort(403, "You are not authorized to view this page.")
        return view(**kwargs)
    return wrapped_view


@bp.route("/admin/")
@admin_login_required
def admin():
    """Admin panel page."""
    db = db_conn()[g.db_name]
    content = {}
    content["users"] = users_stats(db)
    content["db"] = database_stats(db)
    content["etl_log"] = etl_log_stats()
    return render_template("admin/admin.html", content=content)


@bp.route("/admin/add-user/", methods=("GET", "POST"))
@admin_login_required
def add_user():
    """Add new user form page."""
    db = db_conn()[g.db_name]
    form = AddUserForm()
    form.role.choices = [("admin", "admin"), ("user", "user")]
    content = {"form": form}
    # POST method
    if form.validate_on_submit():
        if db.users.find_one({"name": form.username.data}):
            content["error"] = (f"User name {form.username.data} "
                                "already exists.")
        elif form.password.data != form.password_repeat.data:
            content["error"] = "Passwords does not match."
        else:
            pwd_hash = generate_password_hash(form.password.data)
            cur = db.users.insert_one(
                {"name": form.username.data, "role": form.role.data,
                 "password": pwd_hash, "active": True}
            )
            if cur.acknowledged and cur.inserted_id:
                content["info"] = "New user successfully added to database."
            else:
                content["error"] = "Database write error."

    return render_template("admin/add_user.html", content=content)


@bp.route("/admin/edit-user/", methods=("GET", "POST"))
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

        # Check user name
        if form_data["user-name"] != "":
            query["name"] = form_data["user-name"]

        # Check role
        if form_data["role"] != "":
            change["role"] = form_data["role"]

        # Check passwords
        if (form_data["pwd"] != ""
                and form_data["pwd"] == form_data["pwd-repeat"]):
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
        elif len(change) == 0 and not content.get("error", None):
            content["error"] = "Edit fields have been not filled."

    return render_template("admin/edit_user.html", content=content)


@bp.route("/admin/block-user/", methods=("GET", "POST"))
@admin_login_required
def block_user():
    """Block user form page."""
    db = db_conn()[g.db_name]
    content = {}
    content["user_names"] = active_user_names_from_db(db)
    # POST method
    if request.method == "POST":
        form_data = dict(request.form)
        if form_data["user-name"] != "":
            cur = db.users.update_one(
                {"name": form_data["user-name"]},
                {"$set": {"active": False}}
            )
            if cur.raw_result["updatedExisting"]:
                content["info"] = "User successfully blocked."
            else:
                content["error"] = "User data was not updated."
        else:
            content["error"] = "Please select user."

    return render_template("admin/block_user.html", content=content)


@bp.route("/admin/unblock-user/", methods=("GET", "POST"))
@admin_login_required
def unblock_user():
    """Unblock user form page."""
    db = db_conn()[g.db_name]
    content = {}
    content["user_names"] = blocked_user_names_from_db(db)
    # POST method
    if request.method == "POST":
        form_data = dict(request.form)
        if form_data["user-name"] != "":
            cur = db.users.update_one(
                {"name": form_data["user-name"]},
                {"$set": {"active": True}}
            )
            if cur.raw_result["updatedExisting"]:
                content["info"] = "User successfully unblocked."
            else:
                content["error"] = "User data was not updated."
        else:
            content["error"] = "Please select user."

    return render_template("admin/unblock_user.html", content=content)


@bp.route("/admin/view-users/")
@admin_login_required
def view_users():
    """View users page."""
    db = db_conn()[g.db_name]
    content = {}
    content["users"] = users_from_db(db)

    return render_template("admin/view_users.html", content=content)


def size(bytes: int) -> str:
    """Accepts size in bytes as integer and returns size as string
    with Kb, Mb or Gb abbr."""
    if bytes < 1024:
        return str(bytes) + " bytes"
    elif bytes < 1024 ** 2:
        return str(round(bytes / 1024, 1)) + " Kb"
    elif bytes < 1024 ** 3:
        return str(round(bytes / 1024 ** 2, 1)) + " Mb"
    else:
        return str(round(bytes / 1024 ** 3, 1)) + " Gb"


def users_stats(db: Database) -> dict:
    """Prepare and return user stats."""
    stats = {}
    stats["admin"] = db.users.count_documents({"role": "admin"})
    stats["user"] = db.users.count_documents({"role": "user"})
    stats["active"] = db.users.count_documents({"active": True})
    stats["blocked"] = db.users.count_documents({"active": False})
    return stats


def database_stats(db: Database) -> dict:
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


def etl_log_stats() -> dict:
    """Prepare and return etl log stats."""
    stats = {}
    if os.path.exists("logs/one.log"):
        with open("logs/one.log", "r") as f:
            logs = len(f.readlines())
        stats["size"] = size(os.path.getsize("logs/one.log"))
    else:
        stats["size"] = logs = 0
    stats["logs"] = logs
    return stats


def active_user_names_from_db(db: Database) -> list:
    """Returns list of active user names from database."""
    names = []
    cursor = db.users.find({"active": True}, {"_id": 0, "name": 1})
    for c in cursor:
        names.append(c["name"])
    return names


def blocked_user_names_from_db(db: Database) -> list:
    """Returns list of blocked user names from database."""
    names = []
    cursor = db.users.find({"active": False}, {"_id": 0, "name": 1})
    for c in cursor:
        names.append(c["name"])
    return names


def users_from_db(db: Database) -> dict:
    """Returns users info from database."""
    cursor = db.users.find({}, {"_id": 0, "password": 0})
    return json.loads(dumps(cursor))
