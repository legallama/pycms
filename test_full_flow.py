from app import create_app
from app.extensions import db
from app.models.user import User, UserRole

app = create_app()
app.config["WTF_CSRF_ENABLED"] = False
client = app.test_client()

with app.app_context():
    # Ensure test user exists
    user = db.session.execute(db.select(User).where(User.email == "test@example.com")).scalar_one_or_none()
    if not user:
        user = User(email="test@example.com", role=UserRole.ADMIN.value, is_active=True)
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

# Login
login_resp = client.post("/admin/login", data={"email": "test@example.com", "password": "password"}, follow_redirects=True)
print(f"LOGIN CODE: {login_resp.status_code}")

# Get Dashboard
dash_resp = client.get("/admin/")
print(f"DASHBOARD CODE: {dash_resp.status_code}")
if dash_resp.status_code == 500:
    print(dash_resp.data.decode())
