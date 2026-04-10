# PYCMS FRESH BOOT
"""
Template engine — theme loader, position renderer, and Jinja extensions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Line 12
from flask import Flask, current_app, request
from markupsafe import Markup
from jinja2 import BaseLoader, TemplateNotFound

# ... rest of file (omitting for brevity in thought, but I must send the full content)
from .extensions import db
from .models.navigation import Module, Menu, MenuItem


def _themes_root() -> Path:
    """Return the path to the themes directory."""
    return Path(__file__).parent / "themes"


def list_themes() -> list[dict]:
    """Return metadata for every installed theme."""
    themes = []
    root = _themes_root()
    if not root.is_dir():
        return themes
    for d in sorted(root.iterdir()):
        manifest_path = d / "theme.json"
        if d.is_dir() and manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text("utf-8"))
                manifest["_slug"] = d.name
                manifest["_path"] = str(d)
                themes.append(manifest)
            except (json.JSONDecodeError, KeyError):
                pass
    return themes


def get_theme(slug: str | None = None) -> dict | None:
    """Load a single theme manifest. Falls back to the active theme."""
    if slug is None:
        from .models.site_settings import SiteSettings
        settings = SiteSettings.load()
        slug = settings.active_theme

    manifest_path = _themes_root() / slug / "theme.json"
    if not manifest_path.is_file():
        return None

    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest["_slug"] = slug
    manifest["_path"] = str(manifest_path.parent)
    return manifest


def get_positions(theme_slug: str | None = None) -> dict[str, str]:
    """Return {position_id: label} for the active (or given) theme + custom ones."""
    theme = get_theme(theme_slug)
    from .models.site_settings import SiteSettings
    settings = SiteSettings.load()
    try:
        config = json.loads(settings.config_json or "{}")
    except json.JSONDecodeError:
        config = {}
    
    custom_positions = config.get("custom_positions", {})
    
    if not theme:
        base = {"header": "Header", "sidebar": "Sidebar", "footer": "Footer"}
    else:
        base = theme.get("positions", {}).copy()
    
    # Merge custom positions
    base.update(custom_positions)
    return base


def get_layouts(theme_slug: str | None = None) -> dict[str, dict]:
    """Return {layout_id: {label, template}} for the active (or given) theme."""
    theme = get_theme(theme_slug)
    if not theme:
        return {"default": {"label": "Default", "template": "layouts/default.html"}}
    return theme.get("layouts", {})


# ─── Module renderer ───────────────────────────────────────────────────

def _render_module(mod: Module, config: dict) -> str:
    """Render a single module to HTML based on its type."""
    from .models.cms import Post, PublishStatus

    mod_type = mod.type or "html"

    if mod_type == "html":
        return Markup(config.get("html", ""))

    elif mod_type == "text":
        text = config.get("text", "")
        return Markup(f"<p>{text}</p>") if text else Markup("")

    elif mod_type == "menu":
        from .models.navigation import Menu, MenuItem
        menu_name = config.get("menu_name", "main")
        dropdown_width = config.get("dropdown_width", "standard")
        
        menu = db.session.execute(
            db.select(Menu).where(Menu.name == menu_name)
        ).scalar_one_or_none()
        if not menu:
            return Markup("")
        
        items = get_main_menu_items(menu.id)
        
        def render_items(item_list, is_root=True):
            html = ""
            for it in item_list:
                has_children = len(it.get("children", [])) > 0
                cls = "uk-parent" if has_children else ""
                
                icon_html = f'<span uk-icon="{it["icon"]}" class="uk-margin-small-right"></span>' if it.get("icon") else ""
                li_html = f'<li class="{cls}"><a href="{it["href"]}">{icon_html}{it["label"]}</a>'
                if has_children:
                    # Apply width class based on config
                    width_style = ""
                    if dropdown_width == "large":
                        width_style = " uk-navbar-dropdown-large"
                    elif dropdown_width == "xlarge":
                        width_style = " style='width: 400px;'"
                    
                    li_html += f'<div class="uk-navbar-dropdown{width_style}" uk-drop="offset: 0; pos: bottom-center; boundary: !nav; flip: x;"><ul class="uk-nav uk-navbar-dropdown-nav">'
                    li_html += render_items(it["children"], is_root=False)
                    li_html += '</ul></div>'
                li_html += '</li>'
                html += li_html
            return html

        links = Markup(render_items(items))
        return Markup(f'<ul class="uk-navbar-nav">{links}</ul>')

    elif mod_type == "recent_posts":
        count = int(config.get("count", 5))
        posts = db.session.execute(
            db.select(Post)
            .where(Post.status == PublishStatus.PUBLISHED.value)
            .order_by(Post.published_at.desc().nullslast())
            .limit(count)
        ).scalars().all()
        if not posts:
            return Markup("<p>No posts yet.</p>")
        items = Markup("").join(
            Markup(f'<li><a href="/blog/{p.slug}">{p.title}</a></li>') for p in posts
        )
        return Markup(f'<ul class="uk-list uk-list-divider">{items}</ul>')

    elif mod_type == "search":
        return Markup(
            '<form action="/search" method="get">'
            '<div class="uk-inline uk-width-1-1">'
            '<span class="uk-form-icon" uk-icon="icon: search"></span>'
            '<input class="uk-input" type="text" name="q" placeholder="Search...">'
            '</div></form>'
        )

    elif mod_type == "hero":
        image_url = config.get("image_url") or "https://antigravity.google/assets/hero-bg.jpg"
        title = config.get("title", "Hero Title")
        subtitle = config.get("subtitle", "")
        height = config.get("height", "viewport")
        
        # Extended features
        overlay_color = config.get("overlay_color", "#000000")
        overlay_opacity = config.get("overlay_opacity", 0.4)
        align = config.get("align", "center")  # left | center | right
        btn_text = config.get("btn_text", "")
        btn_url = config.get("btn_url", "")
        btn_style = config.get("btn_style", "primary")
        text_shadow = config.get("text_shadow", False)
        parallax = config.get("parallax", True)
        
        height_class = f"uk-height-{height}" if height != "viewport" else "uk-height-viewport"
        # Convert alignment to flex and text classes
        flex_align = "uk-flex-center" if align == "center" else ("uk-flex-right" if align == "right" else "")
        text_align = f"uk-text-{align}"
        
        parallax_attr = 'uk-parallax="bgsfx: 1.1,1; bgy: -100"' if parallax else ''
        shadow_style = "text-shadow: 2px 2px 8px rgba(0,0,0,0.8);" if text_shadow else ""
        
        btn_html = ""
        if btn_text and btn_url:
            btn_html = f'<div class="uk-margin-medium-top"><a href="{btn_url}" class="uk-button uk-button-{btn_style} uk-button-large">{btn_text}</a></div>'
            
        overlay_html = f'<div class="uk-position-cover" style="background-color: {overlay_color}; opacity: {overlay_opacity};"></div>'

        return Markup(
            f'<div class="{height_class} uk-background-cover uk-background-center-center uk-light uk-flex {flex_align} uk-flex-middle uk-position-relative" '
            f'style="background-image: url(\'{image_url}\'); background-color: #1a1a1a;" '
            f'{parallax_attr} uk-img>'
            f'  {overlay_html}'
            f'  <div class="{text_align} uk-padding-large uk-position-relative" style="z-index: 10; {shadow_style}">'
            f'    <div class="uk-container">'
            f'      <h1 class="uk-heading-medium" uk-parallax="opacity: 0.2,1; y: 60,0; viewport: 0.5;">{title}</h1>'
            f'      <p class="uk-text-lead" uk-parallax="opacity: 0.2,1; y: 30,0; viewport: 0.5;">{subtitle}</p>'
            f'      {btn_html}'
            f'    </div>'
            f'  </div>'
            f'</div>'
        )

    elif mod_type == "slider":
        slides = config.get("slides", [])
        autoplay = config.get("autoplay", False)
        interval = config.get("interval", 3000)
        infinite = config.get("infinite", True)
        center = config.get("center", False)
        nav_arrows = config.get("nav_arrows", True)
        nav_dots = config.get("nav_dots", True)
        
        slider_opts = f'autoplay: {str(autoplay).lower()}; autoplay-interval: {interval}; infinite: {str(infinite).lower()}; center: {str(center).lower()};'
        
        items_html = ""
        for s in slides:
            img = s.get("image") or "https://antigravity.google/assets/hero-bg.jpg"
            title = s.get("title", "")
            url = s.get("url", "#")
            
            caption_html = ""
            if title:
                caption_html = f'<div class="uk-position-bottom uk-panel uk-padding uk-light uk-background-gradient-vertical"><h3>{title}</h3></div>'
            
            items_html += (
                f'<li>'
                f'  <div class="uk-inline-hover uk-width-1-1">'
                f'    <a href="{url}">'
                f'      <img src="{img}" alt="{title}" style="width: 100%; height: 400px; object-fit: cover;">'
                f'      {caption_html}'
                f'    </a>'
                f'  </div>'
                f'</li>'
            )
            
        arrows_html = ""
        if nav_arrows:
            arrows_html = (
                '<a class="uk-position-center-left uk-position-small uk-hidden-hover" href="#" uk-slidenav-previous uk-slider-item="previous"></a>'
                '<a class="uk-position-center-right uk-position-small uk-hidden-hover" href="#" uk-slidenav-next uk-slider-item="next"></a>'
            )
            
        dots_html = ""
        if nav_dots:
            dots_html = '<ul class="uk-slider-nav uk-dotnav uk-flex-center uk-margin"></ul>'

        return Markup(
            f'<div uk-slider="{slider_opts}">'
            f'  <div class="uk-position-relative uk-visible-toggle">'
            f'    <ul class="uk-slider-items uk-child-width-1-1 uk-child-width-1-2@s uk-child-width-1-3@m uk-grid-small" uk-grid>'
            f'      {items_html}'
            f'    </ul>'
            f'    {arrows_html}'
            f'  </div>'
            f'  {dots_html}'
            f'</div>'
        )

    elif mod_type == "gallery":
        items = config.get("items", [])
        grid_cols = config.get("grid_cols", "1-3")
        grid_gap = config.get("grid_gap", "small")
        enable_lightbox = config.get("lightbox", True)
        masonry = config.get("masonry", False)
        
        grid_attr = f'uk-grid="masonry: {str(masonry).lower()}"' if masonry else 'uk-grid'
        gap_class = f'uk-grid-{grid_gap}' if grid_gap != 'small' else 'uk-grid-small'
        lightbox_attr = 'uk-lightbox="animation: slide"' if enable_lightbox else ''
        
        items_html = ""
        for item in items:
            img = item.get("image") or ""
            if not img: continue
            caption = item.get("caption", "")
            
            # Use lightbox if enabled
            inner_html = ""
            if enable_lightbox:
                inner_html = (
                    f'<a class="uk-inline-hover uk-display-block" href="{img}" data-caption="{caption}">'
                    f'  <img src="{img}" alt="{caption}" class="uk-transition-scale-up uk-transition-opaque">'
                    f'  <div class="uk-overlay uk-overlay-primary uk-position-bottom uk-transition-fade">'
                    f'    <p>{caption}</p>'
                    f'  </div>'
                    f'</a>'
                )
            else:
                inner_html = (
                    f'<div class="uk-inline-hover">'
                    f'  <img src="{img}" alt="{caption}">'
                    f'  <div class="uk-overlay uk-overlay-primary uk-position-bottom uk-transition-fade">'
                    f'    <p>{caption}</p>'
                    f'  </div>'
                    f'</div>'
                )
            
            items_html += f'<div>{inner_html}</div>'
            
        return Markup(
            f'<div {lightbox_attr}>'
            f'  <div class="{gap_class} uk-child-width-1-1 uk-child-width-{grid_cols}@m" {grid_attr}>'
            f'    {items_html}'
            f'  </div>'
            f'</div>'
        )

    elif mod_type == "media_lightbox":
        items = config.get("items", [])
        grid_cols = config.get("grid_cols", "1-3")
        grid_gap = config.get("grid_gap", "medium")
        
        gap_class = f'uk-grid-{grid_gap}' if grid_gap != 'small' else 'uk-grid-small'
        
        items_html = ""
        for item in items:
            m_type = item.get("type", "image")
            m_url = item.get("url", "")
            if not m_url: continue
            m_thumb = item.get("thumb", "")
            caption = item.get("caption", "")
            
            # Decide on the thumbnail
            display_thumb = m_thumb
            if not display_thumb:
                if m_type == "image":
                    display_thumb = m_url
                else:
                    # Placeholder for videos if no thumb provided
                    display_thumb = "https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?q=80&w=2070&auto=format&fit=crop"

            # Video icon overlay for non-image types
            overlay_icon = ""
            if m_type != "image":
                overlay_icon = '<div class="uk-position-center"><span uk-icon="icon: play-circle; ratio: 3" class="uk-light"></span></div>'
            
            items_html += (
                f'<div>'
                f'  <div class="uk-inline-hover uk-display-block uk-link-reset">'
                f'    <a href="{m_url}" data-caption="{caption}" uk-lightbox>'
                f'      <div class="uk-cover-container uk-height-medium">'
                f'        <img src="{display_thumb}" alt="{caption}" uk-cover class="uk-transition-scale-up uk-transition-opaque">'
                f'        <div class="uk-overlay uk-overlay-primary uk-position-cover uk-transition-fade" style="background: rgba(0,0,0,0.3);"></div>'
                f'        {overlay_icon}'
                f'        <div class="uk-overlay uk-overlay-primary uk-position-bottom uk-padding-small uk-transition-slide-bottom-small">'
                f'          <p class="uk-margin-remove uk-text-truncate">{caption or m_type.capitalize()}</p>'
                f'        </div>'
                f'      </div>'
                f'    </a>'
                f'  </div>'
                f'</div>'
            )
            
        return Markup(
            f'<div class="{gap_class} uk-child-width-1-1 uk-child-width-{grid_cols}@m" uk-grid uk-lightbox="animation: fade">'
            f'  {items_html}'
            f'</div>'
        )

    return ""


def render_position(position_name: str, default_html: str = "") -> str:
    """Render all enabled modules for a given position. Returns safe HTML."""
    from sqlalchemy.orm import joinedload
    from flask import current_app
    is_preview = request.args.get("preview") == "1"
    
    # Fetch all enabled candidate modules for this position
    candidates = db.session.execute(
        db.select(Module)
        .options(joinedload(Module.assigned_items))
        .where(Module.position == position_name, Module.enabled.is_(True))
        .order_by(Module.order.asc())
    ).scalars().unique().all()

    # Filter based on assignment
    current_path = request.path
    modules = []
    for mod in candidates:
        if mod.assignment_type == "all":
            modules.append(mod)
        elif mod.assignment_type == "selected":
            match = False
            for item in mod.assigned_items:
                # Match by exact URL
                if item.url == current_path:
                    match = True; break
                # Match home page variants
                clean_url = (item.url or "/").rstrip("/")
                clean_path = current_path.rstrip("/")
                if (clean_url == "" and clean_path == "") or (clean_url == clean_path):
                    match = True; break
            if match:
                modules.append(mod)

    parts = []
    for mod in modules:
        try:
            config = json.loads(mod.config_json or "{}")
        except json.JSONDecodeError:
            config = {}

        html = _render_module(mod, config)
        if not html:
            continue

        show_title = config.get("show_title", True)
        css_class = mod.css_class or ""

        block = Markup(f'<div class="module-block {css_class}">')
        if show_title and mod.title:
            block += Markup(f'<h4 class="module-title">{mod.title}</h4>')
        block += Markup(f'<div class="module-content">') + html + Markup('</div></div>')
        parts.append(block)

    output = Markup("").join(parts)
    
    # In preview mode, always wrap the position even if empty
    if is_preview:
        label_html = f'<div class="tm-position-preview-label">{position_name}</div>'
        
        # Use default_html if empty and in preview
        preview_body = output if output else Markup(default_html)
        
        overlay_class = "tm-position-preview-active" if preview_body else "tm-position-preview-empty"
        
        output = Markup(f'<div class="tm-position-preview {overlay_class}">{label_html}') + preview_body + Markup('</div>')
        
    return output


# ─── Jinja integration ─────────────────────────────────────────────────

def init_templating(app: Flask) -> None:
    """Register template helpers and the theme template directory."""
    # Add themes template folder to the Jinja loader search path
    themes_dir = _themes_root()

    @app.context_processor
    def _inject_theme_helpers():
        from .models.site_settings import SiteSettings
        import json
        settings = SiteSettings.load()
        try:
            config = json.loads(settings.config_json or "{}")
        except json.JSONDecodeError:
            config = {}
            
        return {
            "render_position": lambda pos, default="": Markup(render_position(pos, default)),
            "get_positions": get_positions,
            "get_layouts": get_layouts,
            "theme_config": config,
            "active_theme": settings.active_theme
        }

    # Also make render_position available as a global
    app.jinja_env.globals["render_position"] = lambda pos, default="": Markup(render_position(pos, default))


def get_main_menu_items(menu_id: int | None = None) -> list[dict]:
    """Return nested list of menu items with children."""
    from .models.navigation import Menu, MenuItem
    
    if menu_id:
        menu = db.session.get(Menu, menu_id)
    else:
        menu = db.session.execute(db.select(Menu).where(Menu.name == "main")).scalar_one_or_none()
    
    if not menu:
        return [{"label": "Home", "href": "/", "children": []}, {"label": "Blog", "href": "/blog", "children": []}]

    all_items = db.session.execute(
        db.select(MenuItem).where(MenuItem.menu_id == menu.id).order_by(MenuItem.order.asc())
    ).scalars().all()

    item_map = {item.id: {"label": item.label, "href": item.url or "/", "icon": item.icon, "children": []} for item in all_items}
    root_items = []
    for item in all_items:
        if item.parent_id and item.parent_id in item_map:
            item_map[item.parent_id]["children"].append(item_map[item.id])
        else:
            root_items.append(item_map[item.id])
    return root_items
