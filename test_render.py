import os
os.environ["FLASK_ENV"] = "development"
os.environ["FLASK_DEBUG"] = "1"

from app import create_app
from flask import render_template, request, url_for

app = create_app()
with app.test_request_context('/admin/'):
    from flask_login import login_user
    from app.models.user import User
    
    with app.app_context():
        # try to render
        try:
            # mock current user
            class MockUser:
                is_authenticated = True
                email = "admin@example.com"
                id = 1
                def get_role(self): return "admin"
            
            from flask_login import login_user
            # We can't easily login_user a mock without a real DB entry if we want all decorators to work,
            # but for simple rendering, setting jinja globals should suffice if the template uses current_user.
            
            app.jinja_env.globals['current_user'] = MockUser()
            app.jinja_env.globals['csrf_token'] = lambda: "mock_token"
            
            print("Rendering dashboard.html...")
            html = render_template('admin/dashboard.html')
            print("RENDER SUCCESS (Dashboard)")

            print("Rendering login.html...")
            from app.admin.forms import LoginForm
            form = LoginForm()
            html = render_template('admin/login.html', form=form)
            print("RENDER SUCCESS (Login)")
        except Exception as e:
            import traceback
            traceback.print_exc()
