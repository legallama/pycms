from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from flask import abort
from flask_login import current_user

from .models.user import UserRole


def require_roles(*roles: UserRole | str) -> Callable:
    allowed = {r.value if isinstance(r, UserRole) else str(r) for r in roles}

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.get_role() not in allowed:
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator

