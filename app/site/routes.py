import json
import shutil
from pathlib import Path
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..auth import require_roles
from ..extensions import db
from ..models.cms import Page, Post
from ..models.navigation import Menu, MenuItem
from ..models.user import UserRole
from ..templating import get_theme, get_positions, get_layouts, list_themes

from ..models.site_settings import SiteSettings
site_bp = Blueprint("site", __name__, template_folder="../templates")


@site_bp.route("/settings", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN)
def site_settings():
    settings = SiteSettings.load()
    if request.method == "POST":
        settings.site_name = (request.form.get("site_name") or "PageCraft").strip()
        settings.posts_per_page = int(request.form.get("posts_per_page") or 10)
        
        db.session.commit()
        flash("Settings updated.", "success")
        return redirect(url_for("site.site_settings"))
        
    return render_template("admin/site/settings.html", settings=settings)


@site_bp.get("/menus")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def menus_list():
    menus = db.session.execute(db.select(Menu).order_by(Menu.name.asc())).scalars().all()
    return render_template("admin/menus/list.html", menus=menus)


@site_bp.route("/menus/new", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def menus_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "danger")
        else:
            existing = db.session.execute(db.select(Menu).where(Menu.name == name)).scalar_one_or_none()
            if existing:
                flash("Menu already exists.", "danger")
            else:
                m = Menu(name=name)
                db.session.add(m)
                db.session.commit()
                return redirect(url_for("site.menus_edit", menu_id=m.id))
    return render_template("admin/menus/new.html")


@site_bp.get("/menus/<int:menu_id>")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def menus_edit(menu_id: int):
    menu = db.session.get(Menu, menu_id)
    if not menu:
        return ("Not Found", 404)
    items = (
        db.session.execute(
            db.select(MenuItem).where(MenuItem.menu_id == menu.id).order_by(MenuItem.parent_id.asc().nullsfirst(), MenuItem.order.asc())
        )
        .scalars()
        .all()
    )
    pages = db.session.execute(db.select(Page).order_by(Page.title.asc())).scalars().all()
    posts = db.session.execute(db.select(Post).order_by(Post.title.asc())).scalars().all()
    return render_template("admin/menus/edit.html", menu=menu, items=items, pages=pages, posts=posts)


@site_bp.post("/menus/<int:menu_id>/items/new")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def menu_items_new(menu_id: int):
    menu = db.session.get(Menu, menu_id)
    if not menu:
        return ("Not Found", 404)

    label = (request.form.get("label") or "").strip()
    if not label:
        flash("Label is required.", "danger")
        return redirect(url_for("site.menus_edit", menu_id=menu.id))

    item_type = (request.form.get("type") or "url").strip().lower()
    url = (request.form.get("url") or "").strip()
    page_slug = (request.form.get("page_slug") or "").strip()
    post_slug = (request.form.get("post_slug") or "").strip()
    icon = (request.form.get("icon") or "").strip()

    if item_type == "url":
        if not url:
            flash("URL is required.", "danger")
            return redirect(url_for("site.menus_edit", menu_id=menu.id))
    elif item_type == "page":
        if not page_slug:
            flash("Pick a page.", "danger")
            return redirect(url_for("site.menus_edit", menu_id=menu.id))
        url = f"/{page_slug}"
    elif item_type == "post":
        if not post_slug:
            flash("Pick a post.", "danger")
            return redirect(url_for("site.menus_edit", menu_id=menu.id))
        url = f"/blog/{post_slug}"
    elif item_type == "shop":
        url = "/shop"
    else:
        flash("Invalid menu item type.", "danger")
        return redirect(url_for("site.menus_edit", menu_id=menu.id))

    parent_id = request.form.get("parent_id")
    if parent_id and parent_id.isdigit():
        parent_id = int(parent_id)
    else:
        parent_id = None

    max_order = (
        db.session.execute(
            db.select(db.func.max(MenuItem.order)).where(MenuItem.menu_id == menu.id, MenuItem.parent_id == parent_id)
        ).scalar()
        or 0
    )

    new_item = MenuItem(
        menu_id=menu.id,
        label=label,
        icon=icon,
        type=item_type,
        url=url,
        page_slug=page_slug if item_type == "page" else None,
        post_slug=post_slug if item_type == "post" else None,
        parent_id=parent_id,
        order=max_order + 1,
    )
    db.session.add(new_item)
    db.session.commit()
    flash("Item added.", "success")
    return redirect(url_for("site.menus_edit", menu_id=menu.id))


@site_bp.post("/menus/items/<int:item_id>/delete")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def menu_items_delete(item_id: int):
    item = db.session.get(MenuItem, item_id)
    if not item:
        abort(404)
    menu_id = item.menu_id
    db.session.delete(item)
    db.session.commit()
    flash("Item removed.", "success")
    return redirect(url_for("site.menus_edit", menu_id=menu_id))


@site_bp.post("/menus/<int:menu_id>/reorder")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def menu_reorder(menu_id: int):
    menu = db.session.get(Menu, menu_id)
    if not menu:
        return {"error": "Menu not found"}, 404
        
    data = request.get_json(silent=True) or {}
    order_data = data.get("order", [])
    print(f"REORDER MENU {menu_id}: {order_data}")
    
    if not order_data:
        return {"error": "No order data provided"}, 400
        
    try:
        for index, item_id in enumerate(order_data):
            item = db.session.get(MenuItem, int(item_id))
            if item and item.menu_id == menu.id:
                item.order = index
                
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}, 500

    return {"status": "ok"}


@site_bp.route("/menus/item/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def menu_item_edit(item_id: int):
    item = db.session.get(MenuItem, item_id)
    if not item:
        abort(404)
    
    # Fetch potential parents for dropdown (excluding self)
    parents = db.session.execute(
        db.select(MenuItem).where(MenuItem.menu_id == item.menu_id, MenuItem.id != item.id, MenuItem.parent_id.is_(None))
    ).scalars().all()
    
    if request.method == "POST":
        item.label = (request.form.get("label") or "").strip()
        item.url = (request.form.get("url") or "").strip()
        item.icon = (request.form.get("icon") or "").strip()
        pid = request.form.get("parent_id")
        item.parent_id = int(pid) if pid and pid.isdigit() else None
        
        if not item.label or not item.url:
            flash("Label and URL are required.", "danger")
        else:
            db.session.commit()
            flash("Item updated.", "success")
            return redirect(url_for("site.menus_edit", menu_id=item.menu_id))

    return render_template("admin/menus/item_edit.html", item=item, items=parents)


@site_bp.post("/menus/<int:menu_id>/delete")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def menus_delete(menu_id: int):
    menu = db.session.get(Menu, menu_id)
    if not menu:
        abort(404)
    if menu.name == "main":
        flash("Cannot delete the system 'main' menu.", "danger")
        return redirect(url_for("site.menus_list"))
    
    db.session.delete(menu)
    db.session.commit()
    flash("Menu deleted.", "success")
    return redirect(url_for("site.menus_list"))


@site_bp.get("/themes")
@login_required
@require_roles(UserRole.ADMIN)
def themes_list():
    from ..models.site_settings import SiteSettings
    themes = list_themes()
    settings = SiteSettings.load()
    return render_template("admin/themes/list.html", themes=themes, active_theme=settings.active_theme)


@site_bp.post("/themes/activate")
@login_required
@require_roles(UserRole.ADMIN)
def themes_activate():
    theme_slug = (request.form.get("theme") or "").strip()
    if not theme_slug:
        flash("No theme specified.", "danger")
        return redirect(url_for("site.themes_list"))

    from ..models.site_settings import SiteSettings
    
    if not get_theme(theme_slug):
        flash(f"Theme '{theme_slug}' not found on disk.", "danger")
        return redirect(url_for("site.themes_list"))

    settings = SiteSettings.load()
    settings.active_theme = theme_slug
    db.session.commit()
    
    flash(f"Theme '{theme_slug}' activated.", "success")
    return redirect(url_for("site.themes_list"))


@site_bp.route("/themes/settings", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN)
def themes_settings():
    import json
    from ..models.site_settings import SiteSettings
    
    settings = SiteSettings.load()
    theme = get_theme(settings.active_theme)
    
    try:
        config = json.loads(settings.config_json or "{}")
    except json.JSONDecodeError:
        config = {}

    if request.method == "POST":
        # Handle position widths
        widths = config.get("position_widths", {})
        all_positions = get_positions(settings.active_theme)
        for pos in all_positions:
            widths[pos] = request.form.get(f"width_{pos}") or "container"
        config["position_widths"] = widths

        # Handle New Position
        new_pos_id = (request.form.get("new_pos_id") or "").strip().lower().replace(" ", "-")
        new_pos_label = (request.form.get("new_pos_label") or "").strip()
        if new_pos_id and new_pos_label:
            custom = config.get("custom_positions", {})
            custom[new_pos_id] = new_pos_label
            config["custom_positions"] = custom
            flash(f"Custom position '{new_pos_label}' added.", "success")

        # Handle Deletion
        del_pos = request.form.get("delete_pos")
        if del_pos:
            custom = config.get("custom_positions", {})
            if del_pos in custom:
                del custom[del_pos]
                config["custom_positions"] = custom
                flash(f"Custom position removed.", "info")

        settings.config_json = json.dumps(config)
        db.session.commit()
        return redirect(url_for("site.themes_settings"))

    return render_template(
        "admin/themes/settings.html",
        theme=theme,
        config=config,
        active_theme_slug=settings.active_theme
    )


@site_bp.post("/themes/delete")
@login_required
@require_roles(UserRole.ADMIN)
def themes_delete():
    theme_slug = (request.form.get("theme") or "").strip()
    if not theme_slug:
        flash("No theme specified.", "danger")
        return redirect(url_for("site.themes_list"))

    if theme_slug == "default":
        flash("The default theme cannot be deleted.", "danger")
        return redirect(url_for("site.themes_list"))

    from ..models.site_settings import SiteSettings
    settings = SiteSettings.load()
    if theme_slug == settings.active_theme:
        flash("Cannot delete the currently active theme.", "danger")
        return redirect(url_for("site.themes_list"))

    from ..templating import _themes_root
    theme_path = _themes_root() / theme_slug
    
    if theme_path.is_dir():
        try:
            shutil.rmtree(theme_path)
            flash(f"Theme '{theme_slug}' deleted.", "success")
        except Exception as e:
            flash(f"Error deleting theme: {str(e)}", "danger")
    else:
        flash("Theme directory not found.", "warning")

    return redirect(url_for("site.themes_list"))
