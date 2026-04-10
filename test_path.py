from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
# Try with backslashes
path = r"C:\Users\MontgomeryKern\OneDrive - Stevens Law Firm\Documents\pycms\instance\app.db"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

from sqlalchemy import text
# Try with 4 slashes
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:////{path}"
with app.app_context():
    try:
        r = db.session.execute(text("SELECT 1")).scalar()
        print(f"4 SLASH SUCCESS: {r}")
    except Exception as e:
        print(f"4 SLASH FAIL: {e}")

# Try with forward slashes
path_f = path.replace("\\", "/")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{path_f}"
with app.app_context():
    try:
        r = db.session.execute(text("SELECT 1")).scalar()
        print(f"FORWARD SLASH SUCCESS: {r}")
    except Exception as e:
        print(f"FORWARD SLASH FAIL: {e}")
