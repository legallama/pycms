import os

from dotenv import load_dotenv
import click
from flask.cli import FlaskGroup

from app import create_app
from app.extensions import db
from app.models.user import User, UserRole


def _create_app():
    load_dotenv()
    return create_app()


cli = FlaskGroup(create_app=_create_app)


@cli.command("create-admin")
@click.argument("email")
@click.argument("password")
def create_admin(email: str, password: str):
    """Create an admin user."""
    app = _create_app()
    with app.app_context():
        existing = db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            raise SystemExit("User already exists.")

        user = User(email=email.strip().lower(), role=UserRole.ADMIN.value, is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Created admin: {user.email}")


@cli.command("run")
def run():
    """Run the dev server.

    Note: this uses Flask's built-in `flask run` under the hood (via FlaskGroup).
    """
    raise SystemExit(
        "Use: .\\.venv\\Scripts\\python manage.py runserver  OR  set FLASK_APP=manage.py and run: flask run"
    )


@cli.command("runserver")
def runserver():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app = _create_app()
    # Flask's CLI intentionally ignores direct calls to app.run() when invoked via
    # click/flask commands. Use Werkzeug directly so `python manage.py runserver`
    # behaves as expected on Windows.
    from werkzeug.serving import run_simple

    debug = True
    run_simple(hostname=host, port=port, application=app, use_debugger=debug, use_reloader=debug)


if __name__ == "__main__":
    cli()

