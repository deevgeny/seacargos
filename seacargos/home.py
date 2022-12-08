import logging

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
from forms import LoginForm
from werkzeug.security import check_password_hash

from db import db_conn

bp = Blueprint("home", __name__)
logger = logging.getLogger("WEB APP")


@bp.before_app_request
def load_logged_in_user():
    """Loads logged in user from session to g object."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = db_conn()[g.db_name]
        g.user = db.users.find_one({"_id": ObjectId(user_id)})


@bp.route("/", methods=("GET", "POST"))
def home():
    """Home page view function (website entry point).

    Functionality:
    - GET - display home page with login form for unauthenticated user.
    - POST - login user to web site.
    """
    form = LoginForm()
    if form.validate_on_submit():
        username = request.form["username"]
        password = request.form["password"]
        db = db_conn()[g.db_name]
        error = None
        user = db.users.find_one({"name": username})

        if not user:
            error = "User with such name does not exist."
        elif not check_password_hash(user["password"], password):
            error = "Incorrect password."
        elif not user["active"]:
            error = "Your login was expired."

        if not error:
            session.clear()
            session["user_id"] = user["_id"].__str__()
            if user["role"] == "user":
                return redirect(url_for("dashboard"))
            if user["role"] == "admin":
                return redirect(url_for("admin"))
        else:
            flash(error)
            logger.error(f"User unseccessful login: {user}")
            return render_template("home/home.html")

    return render_template("home/home.html", form=form)


@bp.route("/logout")
def logout():
    """User logout function."""
    session.clear()
    return redirect(url_for("home"))
