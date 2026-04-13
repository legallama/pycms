import enum
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, login_manager


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    AUTHOR = "author"
    CUSTOMER = "customer"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=UserRole.AUTHOR.value)
    name = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    profile_photo_url = db.Column(db.String(512), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_role(self) -> str:
        return self.role


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))

