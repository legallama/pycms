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
from ..models.shop import Product
from flask import Response
import math
site_bp = Blueprint("site", __name__, template_folder="../templates")


@site_bp.route("/settings", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN)
def site_settings():
    settings = SiteSettings.load()
    try:
        shop_config = json.loads(settings.config_json or "{}")
    except:
        shop_config = {}

    if request.method == "POST":
        settings.site_name = (request.form.get("site_name") or "PageCraft").strip()
        settings.posts_per_page = int(request.form.get("posts_per_page") or 10)
        
        # Postmark settings
        settings.postmark_api_token = request.form.get("postmark_api_token")
        settings.postmark_sender_email = request.form.get("postmark_sender_email")
        
        # Shop Settings (inside config_json)
        shop_config["currency"] = request.form.get("currency") or "USD"
        shop_config["stripe_publishable_key"] = request.form.get("stripe_publishable_key")
        shop_config["stripe_secret_key"] = request.form.get("stripe_secret_key")
        shop_config["paypal_client_id"] = request.form.get("paypal_client_id")
        shop_config["paddle_vendor_id"] = request.form.get("paddle_vendor_id")
        
        # SEO & Analytics settings
        settings.meta_description = request.form.get("meta_description")
        settings.meta_keywords = request.form.get("meta_keywords")
        settings.google_analytics_id = request.form.get("google_analytics_id")
        settings.gemini_api_key = request.form.get("gemini_api_key")
        
        settings.config_json = json.dumps(shop_config)
        db.session.commit()
        
        if request.form.get("action") == "test_email":
            from ..utils.email import send_email
            success = send_email(
                subject="PageCraft - Test Email",
                to_email=settings.postmark_sender_email,
                html_body="<h3>Success!</h3><p>Your Postmark configuration is working correctly.</p>",
                text_body="Success! Your Postmark configuration is working correctly."
            )
            if success:
                flash("Test email sent successfully!", "success")
            else:
                flash("Failed to send test email. Check your settings and logs.", "danger")
        else:
            flash("Settings updated.", "success")
            
        return redirect(url_for("site.site_settings"))
        
    return render_template("admin/site/settings.html", settings=settings, shop_config=shop_config)


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
    from ..models.crm import Form
    forms = db.session.execute(db.select(Form).order_by(Form.name.asc())).scalars().all()
    return render_template("admin/menus/edit.html", menu=menu, items=items, pages=pages, posts=posts, forms=forms)


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
    form_id = request.form.get("form_id")
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
    elif item_type == "form":
        if not form_id:
            flash("Pick a form.", "danger")
            return redirect(url_for("site.menus_edit", menu_id=menu.id))
        url = f"/forms/{form_id}"
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

# --- PUBLIC TOOLS: SEARCH & SITEMAP ---

@site_bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        # Search Pages
        pages = db.session.execute(db.select(Page).where(Page.status == "published", Page.title.ilike(f"%{q}%"))).scalars().all()
        for p in pages:
            results.append({"title": p.title, "url": f"/{p.slug}", "type": "Page", "snippet": p.meta_description})
        
        # Search Posts
        posts = db.session.execute(db.select(Post).where(Post.status == "published", Post.title.ilike(f"%{q}%"))).scalars().all()
        for p in posts:
            results.append({"title": p.title, "url": f"/blog/{p.slug}", "type": "Post", "snippet": p.meta_description})
            
        # Search Products
        products = db.session.execute(db.select(Product).where(Product.is_active == True, Product.name.ilike(f"%{q}%"))).scalars().all()
        for p in products:
            results.append({"title": p.name, "url": f"/shop/product/{p.slug}", "type": "Product", "snippet": p.meta_description})

    # Render using theme logic
    from ..shop.routes import _render_shop_theme
    return _render_shop_theme("search.html", results=results, query=q)

@site_bp.route("/sitemap.xml")
def sitemap():
    pages = db.session.execute(db.select(Page).where(Page.status == "published")).scalars().all()
    posts = db.session.execute(db.select(Post).where(Post.status == "published")).scalars().all()
    products = db.session.execute(db.select(Product).where(Product.is_active == True)).scalars().all()
    
    base_url = request.host_url.rstrip("/")
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    
    # Home
    xml += f'<url><loc>{base_url}/</loc><priority>1.0</priority></url>'
    
    for p in pages:
        xml += f'<url><loc>{base_url}/{p.slug}</loc><lastmod>{p.updated_at.strftime("%Y-%m-%d")}</lastmod><priority>0.8</priority></url>'
    for p in posts:
        xml += f'<url><loc>{base_url}/blog/{p.slug}</loc><lastmod>{p.updated_at.strftime("%Y-%m-%d")}</lastmod><priority>0.6</priority></url>'
    for p in products:
        xml += f'<url><loc>{base_url}/shop/product/{p.slug}</loc><priority>0.7</priority></url>'
        
    xml += '</urlset>'
    return Response(xml, mimetype='application/xml')

def get_seo_warnings():
    warnings = []
    try:
        pages = db.session.execute(db.select(Page)).scalars().all()
        for p in pages:
            if not p.meta_description:
                warnings.append(f"Page '{p.title}' is missing a Meta Description.")
            elif len(p.meta_description) < 50:
                warnings.append(f"Page '{p.title}' has a very short Meta Description.")
            if len(p.title) > 70:
                warnings.append(f"Page '{p.title}' title is too long (> 70 chars).")
                
        posts = db.session.execute(db.select(Post)).scalars().all()
        for p in posts:
            if not p.meta_description:
                warnings.append(f"Post '{p.title}' is missing a Meta Description.")
                
        products = db.session.execute(db.select(Product)).scalars().all()
        for p in products:
            if not p.meta_description:
                warnings.append(f"Product '{p.name}' is missing a Meta Description.")
    except Exception as e:
        print(f"SEO Warning Error: {str(e)}")
            
    return warnings


@site_bp.post("/theme/customize")
@login_required
@require_roles(UserRole.ADMIN)
def theme_customize():
    data = request.get_json() or {}
    settings = SiteSettings.load()
    try:
        config = json.loads(settings.config_json or "{}")
    except:
        config = {}
    
    config["theme_customization"] = {
        "primary_color": data.get("primary_color", "#6366f1"),
        "secondary_color": data.get("secondary_color", "#ec4899"),
        "bg_light": data.get("bg_light", "#ffffff"),
        "text_light": data.get("text_light", "#333333"),
        "bg_dark": data.get("bg_dark", "#111827"),
        "text_dark": data.get("text_dark", "#f3f4f6"),
        "border_radius": data.get("border_radius", "8px"),
        "font_main": data.get("font_main", "Inter"),
        "font_heading": data.get("font_heading", "Inter"),
        "heading_weight": data.get("heading_weight", "700"),
        "heading_transform": data.get("heading_transform", "none"),
        "line_height": data.get("line_height", "1.6"),
        "letter_spacing": data.get("letter_spacing", "normal"),
        "link_style": data.get("link_style", "none"),
        "bg_pattern": data.get("bg_pattern", "none"),
        "gradient_speed": data.get("gradient_speed", "15s"),
        "gradient_angle": data.get("gradient_angle", "-45deg"),
        "nav_height": data.get("nav_height", "80px"),
        "base_font_size": data.get("base_font_size", "16px"),
        "container_width": data.get("container_width", "1200px"),
        "card_shadow": data.get("card_shadow", "shadow"),
        "card_border_width": data.get("card_border_width", "1px"),
        "button_style": data.get("button_style", "standard"),
        "nav_style": data.get("nav_style", "default"),
        "input_style": data.get("input_style", "default"),
        "animation_speed": data.get("animation_speed", "0.2s"),
        "spacing_y": data.get("spacing_y", "40px"),
        "grad_color_1_light": data.get("grad_color_1_light", "#e0e7ff"),
        "grad_color_2_light": data.get("grad_color_2_light", "#fae8ff"),
        "grad_color_1_dark": data.get("grad_color_1_dark", "#312e81"),
        "grad_color_2_dark": data.get("grad_color_2_dark", "#831843"),
        "glow_style": data.get("glow_style", "ambient")
    }
    
    settings.config_json = json.dumps(config)
    db.session.commit()
    return {"status": "success"}
