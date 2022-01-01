import os
import tempfile
import mongomock

import pytest
from seacargos import create_app
from seacargos.db import db_conn

#with open(os.path.join(os.path.dirname(__file__), 'data.sql'), 'rb') as f:
#    _data_sql = f.read().decode('utf8')

@pytest.fixture
def app():
    #db_fd, db_path = tempfile.mkstemp()
    app = create_app({
        'TESTING': True,
        'DB_FRONTEND_URI': "",
    })

    #with app.app_context():
        #init_db()
        #get_db().executescript(_data_sql)

    yield app

    #os.close(db_fd)
    #os.unlink(db_path)

@pytest.fixture
def client(app):
    return app.test_client()

#@pytest.fixture
#def runner(app):
#    return app.test_cli_runner()
