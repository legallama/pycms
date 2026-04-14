import json
from datetime import datetime, timezone
from flask import request, current_app
from flask_login import current_user
from itsdangerous import URLSafeTimedSerializer
from ..extensions import db

def log_action(action: str, details: str = None, target_type: str = None, target_id: int = None):
    from ..models.cms import AuditLog
    log = AuditLog(
        user_id=current_user.id if (current_user and current_user.is_authenticated) else None,
        action=action,
        details=details,
        target_type=target_type,
        target_id=target_id,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()

def save_revision(target: db.Model, note: str = ""):
    from ..models.cms import Revision
    # Simple serialization of model columns
    data = {}
    for column in target.__table__.columns:
        val = getattr(target, column.name)
        if isinstance(val, (datetime,)):
            val = val.isoformat()
        data[column.name] = val
        
    rev = Revision(
        target_type=target.__tablename__.rstrip('s'), # page or post
        target_id=target.id,
        user_id=current_user.id,
        data_json=json.dumps(data),
        note=note
    )
    db.session.add(rev)
    db.session.commit()

class PreviewHelper:
    @staticmethod
    def get_serializer():
        return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

    @classmethod
    def generate_token(cls, target_type: str, target_id: int):
        serializer = cls.get_serializer()
        return serializer.dumps({"type": target_type, "id": target_id}, salt="preview")

    @classmethod
    def verify_token(cls, token: str, max_age: int = 86400):
        serializer = cls.get_serializer()
        try:
            return serializer.loads(token, salt="preview", max_age=max_age)
        except:
            return None
