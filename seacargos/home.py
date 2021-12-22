from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
from seacargos.db import get_conn

bp = Blueprint('home', __name__)

@bp.route('/')
def index():
    conn = get_conn()
    db = conn.seacargos
    content = {}
    content["vessels"] = db.vessels.count_documents({})
    content["users"] = db.users.count_documents({})
    content["shipments"] = db.shipments.count_documents({})
    content["tracking"] = db.tracking.count_documents({})
    return render_template('home/index.html', content=content)
