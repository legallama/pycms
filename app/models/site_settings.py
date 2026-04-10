"""SiteSettings model — single-row table for global site configuration."""
from ..extensions import db


class SiteSettings(db.Model):
    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(255), nullable=False, default="pycms")
    active_theme = db.Column(db.String(100), nullable=False, default="default")
    config_json = db.Column(db.Text, nullable=False, default="{}")

    @classmethod
    def load(cls) -> "SiteSettings":
        """Return the single settings row, creating it if needed."""
        row = db.session.execute(db.select(cls)).scalar_one_or_none()
        if not row:
            row = cls(id=1, site_name="pycms", active_theme="default")
            db.session.add(row)
            db.session.commit()
        return row
