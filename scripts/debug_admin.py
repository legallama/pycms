from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.user import User  # noqa: E402


def _extract_csrf_token(html: bytes) -> str | None:
    # WTForms renders csrf like: name="csrf_token" type="hidden" value="..."
    m = re.search(rb'name="csrf_token"\s+type="hidden"\s+value="([^"]+)"', html)
    return m.group(1).decode("utf-8") if m else None


def main() -> None:
    app = create_app()
    app.config["TESTING"] = False

    with app.app_context():
        # Ensure we can log in during debugging by setting a known password
        # on the first user in the database (or admin@example.com if present).
        user = db.session.execute(db.select(User).where(User.email == "admin@example.com")).scalar_one_or_none()
        if user is None:
            user = db.session.execute(db.select(User).order_by(User.id.asc())).scalar_one_or_none()
        if user is not None:
            user.set_password("Password123!")
            db.session.commit()
            print(f"Set password for {user.email} to Password123!")
        else:
            print("No users found in DB; cannot test authenticated /admin/")

        c = app.test_client()

        print("GET /admin/")
        r = c.get("/admin/", follow_redirects=False)
        print(" status:", r.status_code)
        print(" location:", r.headers.get("Location"))

        print("\nGET /admin/login")
        r = c.get("/admin/login", follow_redirects=False)
        print(" status:", r.status_code)
        print(" len:", len(r.data))

        token = _extract_csrf_token(r.data) or ""
        print(" csrf token found:", bool(token))

        print("\nPOST /admin/login (invalid creds)")
        try:
            r2 = c.post(
                "/admin/login",
                data={"email": "x@example.com", "password": "password123", "csrf_token": token},
                follow_redirects=False,
            )
            print(" status:", r2.status_code)
            print(" location:", r2.headers.get("Location"))
            print(" body head:", r2.data[:160])
        except Exception:
            traceback.print_exc()

        if user is not None:
            print("\nPOST /admin/login (known creds)")
            try:
                r3 = c.post(
                    "/admin/login",
                    data={"email": user.email, "password": "Password123!", "csrf_token": token},
                    follow_redirects=False,
                )
                print(" status:", r3.status_code)
                print(" location:", r3.headers.get("Location"))

                print("\nGET /admin/ (after login)")
                r4 = c.get("/admin/", follow_redirects=False)
                print(" status:", r4.status_code)
                print(" location:", r4.headers.get("Location"))
                print(" body head:", r4.data[:160])
            except Exception:
                traceback.print_exc()


if __name__ == "__main__":
    main()

