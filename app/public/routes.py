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

