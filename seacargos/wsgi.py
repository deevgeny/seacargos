import os

from config import create_app

os.environ["FLASK_ENV"] = "production"
app = create_app()
