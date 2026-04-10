from datetime import datetime, timezone

from ..extensions import db


class MediaFile(db.Model):
    __tablename__ = "media_files"

    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(500), unique=True, nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    mime = db.Column(db.String(100), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

