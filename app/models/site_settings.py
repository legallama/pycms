"""SiteSettings model — single-row table for global site configuration."""
from ..extensions import db


class SiteSettings(db.Model):
    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(255), nullable=False, default="PageCraft")
    active_theme = db.Column(db.String(100), nullable=False, default="default")
    config_json = db.Column(db.Text, nullable=False, default="{}")
    posts_per_page = db.Column(db.Integer, nullable=False, default=10)
    
    # Mail Settings (Postmark)
    postmark_api_token = db.Column(db.String(255), nullable=True)
    postmark_sender_email = db.Column(db.String(255), nullable=True)

    # SEO & Analytics Settings
    meta_description = db.Column(db.Text, nullable=True)
    meta_keywords = db.Column(db.String(500), nullable=True)
    google_analytics_id = db.Column(db.String(50), nullable=True)
    gemini_api_key = db.Column(db.String(255), nullable=True)

    @classmethod
    def load(cls) -> "SiteSettings":
        """Return the single settings row, creating it if needed."""
        row = db.session.execute(db.select(cls)).scalar_one_or_none()
        if not row:
            row = cls(id=1, site_name="PageCraft", active_theme="default")
            db.session.add(row)
            db.session.commit()
        return row
