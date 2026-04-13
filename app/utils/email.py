import logging
from postmark import PMMail
from flask import current_app
from ..models.site_settings import SiteSettings

logger = logging.getLogger(__name__)

def send_email(subject, to_email, html_body, text_body=None):
    """Send an email using Postmark."""
    settings = SiteSettings.load()
    
    api_token = settings.postmark_api_token
    sender = settings.postmark_sender_email
    
    if not api_token or not sender:
        logger.warning("Postmark not configured. Email could not be sent.")
        return False

    try:
        message = PMMail(
            api_key=api_token,
            subject=subject,
            to=to_email,
            sender=sender,
            text_body=text_body or "",
            html_body=html_body
        )
        message.send()
        logger.info(f"Email sent to {to_email} with subject: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email via Postmark: {str(e)}")
        return False
