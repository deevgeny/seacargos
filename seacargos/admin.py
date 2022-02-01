# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
import functools
from werkzeug.exceptions import abort
from seacargos.db import db_conn

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
    content["vessels"] = db.vessels.count_documents({})
    content["users"] = db.users.count_documents({})
    content["tracking"] = db.tracking.count_documents({})
    content["logs"] = db.logs.count_documents({})
    content['user'] = g.user
    return render_template('admin/admin.html', content=content)
