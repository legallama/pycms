from app import create_app
from app.extensions import db
from app.models.user import User, UserRole

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False  # Disable to test POST easily
client = app.test_client()

with app.app_context():
    # Make sure admin exists
    admin = db.session.execute(db.select(User).where(User.email == "testadmin@test.com")).scalar_one_or_none()
    if not admin:
        admin = User(email="testadmin@test.com", role=UserRole.ADMIN.value, is_active=True)
        admin.set_password("pass")
        db.session.add(admin)
        db.session.commit()

# POST to login
response = client.post('/admin/login', data={'email': 'testadmin@test.com', 'password': 'pass'}, follow_redirects=True)
print("Login POST Status:", response.status_code)
if response.status_code == 500:
    print("LOGIN 500 ERROR:", response.get_data(as_text=True))

# Get dashboard
response = client.get('/admin/')
print("Dashboard GET Status:", response.status_code)
if response.status_code == 500:
    print("DASHBOARD 500 ERROR:", response.get_data(as_text=True))

