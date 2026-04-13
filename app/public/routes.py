from flask import Blueprint, current_app, render_template, abort, request

from ..extensions import db
from ..models.cms import Page, Post, PublishStatus
from ..models.site_settings import SiteSettings
from ..templating import get_theme, get_layouts, get_main_menu_items

public_bp = Blueprint("public", __name__)


def _render_theme(template_name: str, **context):
    """Helper to render a template within the active theme."""
    settings = SiteSettings.load()
    theme = settings.active_theme
    
    # Try to find an assigned menu from the current content (page or post)
    menu_id = None
    if "page" in context:
        menu_id = getattr(context["page"], "menu_id", None)
    
    # Template name is relative to themes/ folder because of ChoiceLoader
    return render_template(f"{theme}/templates/{template_name}", 
                           main_menu_items=get_main_menu_items(menu_id),
                           **context)


@public_bp.get("/")
def home():
    return _render_theme("home.html")


@public_bp.get("/blog")
def blog_index():
    page_num = request.args.get('page', 1, type=int)
    settings = SiteSettings.load()
    per_page = settings.posts_per_page
    
    pagination = db.paginate(
        db.select(Post)
        .where(Post.status == PublishStatus.PUBLISHED.value)
        .order_by(Post.published_at.desc().nullslast(), Post.updated_at.desc()),
        page=page_num,
        per_page=per_page
    )
    return _render_theme("blog/index.html", pagination=pagination)


@public_bp.get("/blog/<slug>")
def blog_post(slug: str):
    post = db.session.execute(
        db.select(Post).where(Post.slug == slug, Post.status == PublishStatus.PUBLISHED.value)
    ).scalar_one_or_none()
    if not post:
        abort(404)
    return _render_theme("blog/post.html", post=post)


@public_bp.get("/<slug>")
def page(slug: str):
    page_obj = db.session.execute(
        db.select(Page).where(Page.slug == slug, Page.status == PublishStatus.PUBLISHED.value)
    ).scalar_one_or_none()
    
    if not page_obj:
        abort(404)
        
    # Determine layout template
    settings = SiteSettings.load()
    layouts = get_layouts()
    layout_cfg = layouts.get(page_obj.layout, layouts.get("default"))
    layout_template = f"{settings.active_theme}/templates/{layout_cfg['template']}"
    
    # Try to render page.html, otherwise fall back to layout
    # (page.html should use '{% extends layout_template %}')
    try:
        return _render_theme("page.html", page=page_obj, layout_template=layout_template)
    except TemplateNotFound:
        return _render_theme(layout_cfg["template"], page=page_obj, layout_template=layout_template)

@public_bp.errorhandler(404)
def not_found(e):
    return _render_theme("404.html"), 404


@public_bp.get("/sitemap.xml")
def sitemap():
    """Generate dynamic XML sitemap."""
    from datetime import datetime
    from flask import Response, make_response
    from ..models.shop import Product
    
    pages = db.session.execute(db.select(Page).where(Page.status == PublishStatus.PUBLISHED.value)).scalars().all()
    posts = db.session.execute(db.select(Post).where(Post.status == PublishStatus.PUBLISHED.value)).scalars().all()
    products = db.session.execute(db.select(Product).where(Product.is_active == True)).scalars().all()
    
    base_url = request.host_url.rstrip("/")
    xml_items = []
    
    # Static & Home
    xml_items.append(f"<url><loc>{base_url}/</loc><priority>1.0</priority></url>")
    xml_items.append(f"<url><loc>{base_url}/blog</loc><priority>0.8</priority></url>")
    xml_items.append(f"<url><loc>{base_url}/shop</loc><priority>0.8</priority></url>")
    
    for p in pages:
        xml_items.append(f"<url><loc>{base_url}/{p.slug}</loc><lastmod>{p.updated_at.date()}</lastmod><priority>0.7</priority></url>")
        
    for p in posts:
        xml_items.append(f"<url><loc>{base_url}/blog/{p.slug}</loc><lastmod>{p.updated_at.date()}</lastmod><priority>0.6</priority></url>")

    for p in products:
        xml_items.append(f"<url><loc>{base_url}/shop/product/{p.slug}</loc><priority>0.6</priority></url>")
        
    xml_content = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{"".join(xml_items)}</urlset>'
    
    response = make_response(xml_content)
    response.headers["Content-Type"] = "application/xml"
    return response


@public_bp.get("/robots.txt")
def robots():
    """Generate robots.txt."""
    from flask import make_response
    content = f"User-agent: *\nAllow: /\nSitemap: {request.host_url}sitemap.xml"
    response = make_response(content)
    response.headers["Content-Type"] = "text/plain"
    return response


@public_bp.get("/forms/<int:form_id>")
def view_form_public(form_id: int):
    from ..models.crm import Form
    import json
    form = db.session.get(Form, form_id)
    if not form: abort(404)
    try:
        fields = json.loads(form.fields_json)
    except:
        fields = []
    
    # Render standalone form view extending theme base
    return _render_theme("crm/form.html", form=form, fields=fields)
