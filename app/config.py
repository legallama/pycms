import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///instance/app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    WTF_CSRF_ENABLED = True

    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "instance/uploads")
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:5000")

    DEBUG = os.environ.get("FLASK_ENV", "").lower() == "development"

