from app import create_app
from app.extensions import db
from app.models.user import User

app = create_app()
client = app.test_client()
with app.app_context():
    # just in case we need a user
    pass

# Try getting login page
response = client.get('/admin/login')
print("Login GET:", response.status_code)

# Try getting dashboard
response = client.get('/admin/')
print("Dashboard redirect:", response.status_code)

# Let's bypass login and force a logged-in request to /admin/
with client.session_transaction() as sess:
    sess['_user_id'] = '1'  # flask-login uses _user_id usually

response = client.get('/admin/')
print("Dashboard logged in:", response.status_code)
if response.status_code == 500:
    print(response.get_data(as_text=True))
