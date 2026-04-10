from app import create_app
from app.extensions import db
from app.models.user import User

app = create_app()
with app.app_context():
    users = db.session.execute(db.select(User)).scalars().all()
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}, Role: {u.role}")
