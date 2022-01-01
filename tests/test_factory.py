from seacargos import create_app
from flask import g


def test_config():
    assert not create_app().testing
    assert create_app({'TESTING': True}).testing

def test_home(client, app):
    response = client.get("/")
    assert response.status_code == 200
    #assert response.data == "x"
    #with app.app_context():
    #    assert g.user == None
