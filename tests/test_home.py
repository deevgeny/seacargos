from seacargos import create_app
from flask import g

def test_home(client, app):
    """Test home page for unauthenticated user."""
    with app.app_context():
        response = client.get("/")
        assert response.status_code == 200
        assert g.user == None