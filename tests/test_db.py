import mongomock
import pytest
from seacargos.db import db_conn, setup_db

def test_db_conn(app):
    """Test db_conn() function from db.py"""
    with app.app_context():
        conn = db_conn()
        assert conn is db_conn()
