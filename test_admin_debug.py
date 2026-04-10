"""Reproduce the admin Internal Server Error with full traceback."""
import traceback
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User

app = create_app()
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True

with app.test_client() as client:
    # 1) Test login page (standalone, no base.html)
    print("=== GET /admin/login ===")
    try:
        resp = client.get('/admin/login')
        print(f"  Status: {resp.status_code}")
    except Exception:
        traceback.print_exc()

    # 2) Test /admin/ without login (should redirect)
    print("\n=== GET /admin/ (not logged in) ===")
    try:
        resp = client.get('/admin/')
        print(f"  Status: {resp.status_code}")
        print(f"  Location: {resp.headers.get('Location', 'none')}")
    except Exception:
        traceback.print_exc()

    # 3) Test /admin/ following redirects (renders login page)
    print("\n=== GET /admin/ follow_redirects (not logged in) ===")
    try:
        resp = client.get('/admin/', follow_redirects=True)
        print(f"  Status: {resp.status_code}")
        body = resp.data.decode()
        if 'Welcome back' in body:
            print("  -> Login page rendered OK")
        elif 'Internal Server Error' in body or resp.status_code == 500:
            print(f"  -> ERROR! Body:\n{body[:3000]}")
    except Exception:
        traceback.print_exc()

    # 4) Force login and test dashboard (uses base.html)
    print("\n=== Force login + GET /admin/ ===")
    @app.login_manager.request_loader
    def load_user_from_request(request):
        return db.session.execute(
            db.select(User).where(User.email == 'admin@example.com')
        ).scalar_one_or_none()

    try:
        resp = client.get('/admin/')
        print(f"  Status: {resp.status_code}")
        body = resp.data.decode()
        if resp.status_code == 500:
            print(f"  -> 500 ERROR! Body:\n{body[:5000]}")
        elif 'Dashboard' in body:
            print("  -> Dashboard rendered OK")
        else:
            print(f"  -> Unknown page: {body[:500]}")
    except Exception:
        traceback.print_exc()

    # 5) Test each page that extends base.html
    print("\n=== Testing other admin pages (authenticated) ===")
    for ep in ['/admin/users', '/admin/users/new']:
        try:
            resp = client.get(ep)
            print(f"  {ep}: {resp.status_code}")
            if resp.status_code == 500:
                print(f"    ERROR: {resp.data.decode()[:1000]}")
        except Exception as e:
            print(f"  {ep}: EXCEPTION - {e}")
            traceback.print_exc()
