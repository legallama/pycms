from app import create_app
from app.extensions import db
from app.models.user import User, UserRole

app = create_app()
app.config["WTF_CSRF_ENABLED"] = False
client = app.test_client()

with app.app_context():
    user = db.session.execute(db.select(User).where(User.email == "test@example.com")).scalar_one_or_none()
    if not user:
        user = User(email="test@example.com", role=UserRole.ADMIN.value, is_active=True)
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

# Authenticate first
client.post("/admin/login", data={"email": "test@example.com", "password": "password"})

endpoints = [
    "/admin/",
    "/admin/pages",
    "/admin/posts",
    "/admin/media",
    "/admin/crm",
    "/admin/crm/contacts",
    "/admin/menus",
    "/admin/modules",
    "/admin/users"
]

for ep in endpoints:
    resp = client.get(ep)
    print(f"{ep}: {resp.status_code}")
    if resp.status_code == 500:
        print(f"ERROR on {ep}:")
        print(resp.data.decode()[:500])
