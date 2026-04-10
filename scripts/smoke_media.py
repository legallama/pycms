import base64
import io
import re

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from manage import _create_app  # noqa: E402


def _extract_csrf(html: str) -> str:
    # Flask-WTF may render either:
    # - <input id="csrf_token" name="csrf_token" type="hidden" value="...">
    # - OR a bare token in some templates via {{ csrf_token() }}
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if not m:
        # Fallback: look for value attribute without name order guarantees.
        m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html)
    if not m:
        raise RuntimeError("Could not find csrf_token in HTML")
    return m.group(1)


def main():
    app = _create_app()
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()

    resp = client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "ChangeMeNow!"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Upload a 1x1 png
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    png = base64.b64decode(png_b64)

    resp = client.post(
        "/admin/media/upload",
        data={"file": (io.BytesIO(png), "dot.png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Ensure listing page contains the filename
    html = resp.get_data(as_text=True)
    assert "dot.png" in html

    print("media smoke test OK")


if __name__ == "__main__":
    main()

