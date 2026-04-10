import enum
from datetime import datetime, timezone

from ..extensions import db


class PublishStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Page(db.Model):
    __tablename__ = "pages"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    body_html = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default=PublishStatus.DRAFT.value)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    layout = db.Column(db.String(50), nullable=False, default="default")
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id"), nullable=True)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    body_html = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default=PublishStatus.DRAFT.value)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

