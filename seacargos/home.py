# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, session, request, url_for
)
from werkzeug.exceptions import abort
from werkzeug.security import check_password_hash, generate_password_hash
from seacargos.db import db_conn
from bson.objectid import ObjectId

bp = Blueprint("home", __name__)

@bp.before_app_request
def load_logged_in_user():
    """Loads logged in user from session to g."""
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        db = db_conn()[g.db_name]
        g.user = db.users.find_one({"_id": ObjectId(user_id)})

@bp.route("/", methods=("GET", "POST"))
def home():
    """Home view function (website entry point)."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = db_conn()[g.db_name]
        error = None
        user = db.users.find_one({"name": username})

        if user is None:
            error = "User with such name does not exist."
        elif not check_password_hash(user["password"], password):
            error = "Incorrect password."

        if error is None:
            session.clear()
            session["user_id"] = user["_id"].__str__()
            if user["role"] == "user":
                return redirect(url_for("dashboard"))
            if user["role"] == "admin":
                return redirect(url_for("admin"))
        else:
            flash(error)
    
    return render_template("home/home.html")

@bp.route("/logout")
def logout():
    """Logout function."""
    session.clear()
    return redirect(url_for("home"))
