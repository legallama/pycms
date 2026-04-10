from ..extensions import db
from .constants import MODULE_TYPES

class Menu(db.Model):
    __tablename__ = "menus"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    @staticmethod
    def ensure_main_menu():
        """Ensure the 'main' menu exists and return it."""
        from ..extensions import db
        menu = db.session.execute(db.select(Menu).where(Menu.name == "main")).scalar_one_or_none()
        if not menu:
            menu = Menu(name="main")
            db.session.add(menu)
            db.session.commit()
        return menu


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id"), nullable=False, index=True)
    type = db.Column(db.String(30), nullable=False, default="url")  # url | page | post
    label = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(100), nullable=True)  # UIkit icon name
    url = db.Column(db.String(500), nullable=True)
    page_slug = db.Column(db.String(200), nullable=True)
    post_slug = db.Column(db.String(200), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=True, index=True)
    order = db.Column(db.Integer, nullable=False, default=0)


module_assignments = db.Table(
    "module_assignments",
    db.Column("module_id", db.Integer, db.ForeignKey("modules.id"), primary_key=True),
    db.Column("menu_item_id", db.Integer, db.ForeignKey("menu_items.id"), primary_key=True),
)


class Module(db.Model):
    __tablename__ = "modules"

    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.String(50), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, default="")
    type = db.Column(db.String(50), nullable=False, default="html")
    config_json = db.Column(db.Text, nullable=False, default="{}")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    order = db.Column(db.Integer, nullable=False, default=0)
    css_class = db.Column(db.String(255), nullable=False, default="")
    show_title = db.Column(db.Boolean, nullable=False, default=True)
    
    # Pagekit-style assignment
    assignment_type = db.Column(db.String(20), nullable=False, default="all")  # all | none | selected
    assigned_items = db.relationship("MenuItem", secondary=module_assignments, backref="assigned_modules")
