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
    meta_description = db.Column(db.Text, nullable=True)
    meta_keywords = db.Column(db.String(500), nullable=True)
    views = db.Column(db.Integer, nullable=False, default=0)


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
    meta_description = db.Column(db.Text, nullable=True)
    meta_keywords = db.Column(db.String(500), nullable=True)
    views = db.Column(db.Integer, nullable=False, default=0)


class Revision(db.Model):
    __tablename__ = "revisions"
    id = db.Column(db.Integer, primary_key=True)
    target_type = db.Column(db.String(50), nullable=False) # 'page' or 'post'
    target_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    data_json = db.Column(db.Text, nullable=False) # Full snapshot
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    note = db.Column(db.String(255), nullable=True)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, nullable=True)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(45), nullable=True)

