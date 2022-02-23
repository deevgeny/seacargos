# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
import functools
from werkzeug.exceptions import abort
from seacargos.db import db_conn
import os

bp = Blueprint('admin', __name__)

def admin_login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('home.home'))
        elif g.user['role'] != 'admin':
            abort(403, 'You are not authorized to view this page.')
        return view(**kwargs)
    return wrapped_view

@bp.route('/admin')
@admin_login_required
def admin():
    db = db_conn()[g.db_name]
    content = {}
    content["users"] = users(db)
    content["db"] = database(db)
    content["etl_log"] = etl_logs()
    #flash("test message")
    return render_template('admin/admin.html', content=content)

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
    stats = {}
    stats["admin"] = db.users.count_documents({"role": "admin"})
    stats["user"] = db.users.count_documents({"role": "user"})
    return stats

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
    cwd = os.getcwd()
    with open("etl.log", "r") as f:
        logs = len(f.readlines())
    stats["logs"] = logs
    stats["size"] = size(os.path.getsize("etl.log"))
    return stats
