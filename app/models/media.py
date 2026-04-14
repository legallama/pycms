from datetime import datetime, timezone

from ..extensions import db


class MediaFolder(db.Model):
    __tablename__ = "media_folders"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("media_folders.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    media_files = db.relationship("MediaFile", back_populates="folder")
    subfolders = db.relationship("MediaFolder", backref=db.backref("parent", remote_side=[id]))

class MediaFile(db.Model):
    __tablename__ = "media_files"

    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(500), unique=True, nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    mime = db.Column(db.String(100), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    folder_id = db.Column(db.Integer, db.ForeignKey("media_folders.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # New advanced fields
    alt_text = db.Column(db.String(500), nullable=True)
    caption = db.Column(db.Text, nullable=True)
    focal_point_x = db.Column(db.Integer, nullable=False, default=50) # Percentage 0-100
    focal_point_y = db.Column(db.Integer, nullable=False, default=50) # Percentage 0-100
    webp_path = db.Column(db.String(500), nullable=True)
    responsive_data = db.Column(db.JSON, nullable=True) # Paths to Thumb, Med, Lrg

    folder = db.relationship("MediaFolder", back_populates="media_files")

