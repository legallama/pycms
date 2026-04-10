from app import create_app
from app.models.user import User
from app.extensions import db

app = create_app()
with app.app_context():
    try:
        u = db.session.get(User, 1)
        print(f"ID 1: {u.email if u else 'None'}")
    except Exception as e:
        print(f"LOAD ERROR: {e}")
