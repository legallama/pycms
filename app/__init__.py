from flask import Flask

from .config import Config
from .extensions import db, migrate, login_manager, csrf
from .admin.routes import admin_bp
from .public.routes import public_bp
from .cms.routes import cms_bp
from .media.routes import media_bp
from .site.routes import site_bp
from .modules.routes import modules_bp
from .crm.routes import crm_bp
from .shop.routes import shop_bp


from typing import Optional
from flask import session

def create_app(config_object: Optional[type[Config]] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)

    # Ensure instance folder exists for SQLite DB and uploads.
    app.instance_path  # access triggers path computation
    try:
        import os

        os.makedirs(app.instance_path, exist_ok=True)
        # Make SQLite path deterministic and Windows-friendly by anchoring it
        # to the Flask instance folder.
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
        if db_uri.startswith("sqlite:///") and not db_uri.startswith("sqlite:////"):
            rel_path = db_uri.removeprefix("sqlite:///")
            if rel_path.startswith("instance/") or rel_path.startswith("instance\\"):
                sqlite_path = os.path.join(app.instance_path, rel_path.split("/", 1)[-1].split("\\", 1)[-1])
                app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_path}"

        upload_dir = app.config.get("UPLOAD_DIR")
        if upload_dir:
            if not os.path.isabs(upload_dir):
                upload_dir = os.path.join(app.instance_path, "uploads")
                app.config["UPLOAD_DIR"] = upload_dir
            os.makedirs(upload_dir, exist_ok=True)
    except OSError:
        # If the environment restricts filesystem ops, app can still run read-only.
        pass

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Template engine (theme positions, module renderer, Jinja helpers)
    from .templating import init_templating
    init_templating(app)

    # Add theme template directories to the Jinja loader
    import os
    from jinja2 import FileSystemLoader, ChoiceLoader
    themes_dir = os.path.join(os.path.dirname(__file__), "themes")
    app.jinja_loader = ChoiceLoader([
        app.jinja_loader,
        FileSystemLoader(themes_dir),
    ])

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(cms_bp, url_prefix="/admin")
    app.register_blueprint(media_bp, url_prefix="/admin")
    app.register_blueprint(site_bp, url_prefix="/admin")
    app.register_blueprint(modules_bp, url_prefix="/admin")
    app.register_blueprint(crm_bp, url_prefix="/admin")
    app.register_blueprint(shop_bp)

    @app.context_processor
    def inject_cart():
        try:
            cart = session.get("cart", {})
            count = sum(item.get("quantity", 0) for item in cart.values())
        except:
            count = 0
        return dict(cart_count=count)

    with app.app_context():
        from .models.navigation import Menu
        try:
            Menu.ensure_main_menu()
        except:
            pass

    return app

