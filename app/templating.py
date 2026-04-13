# PYCMS FRESH BOOT
"""
Template engine — theme loader, position renderer, and Jinja extensions.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

# Line 12
from flask import Flask, current_app, request
from flask_wtf.csrf import generate_csrf
from markupsafe import Markup
from jinja2 import BaseLoader, TemplateNotFound
import json

def from_json_filter(value):
    try:
        return json.loads(value)
    except:
        return []

def slugify_filter(value):
    import re
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')

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


def get_theme(slug: Optional[str] = None) -> Optional[dict]:
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


def get_positions(theme_slug: Optional[str] = None) -> dict[str, str]:
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


def get_layouts(theme_slug: Optional[str] = None) -> dict[str, dict]:
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
        return Markup(process_shortcodes(config.get("html", "")))

    elif mod_type == "text":
        text = config.get("text", "")
        return Markup(f"<p>{process_shortcodes(text)}</p>") if text else Markup("")

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

    elif mod_type == "product_grid":
        from .models.shop import Product
        count = config.get("count", 4)
        cols = config.get("columns", "1-4")
        show_price = config.get("show_price", True)
        
        products = db.session.execute(db.select(Product).where(Product.is_active == True).order_by(Product.created_at.desc()).limit(count)).scalars().all()
        
        csrf = generate_csrf()
        html = f'<div class="uk-grid-small uk-child-width-{cols}@m uk-child-width-1-2" uk-grid>'
        for p in products:
            img = f'<img src="{p.image_url}" alt="{p.name}" style="height: 200px; width: 100%; object-fit: cover;">' if p.image_url else '<div class="uk-background-muted" style="height: 200px;"></div>'
            price_html = f'<p class="uk-text-bold uk-margin-small-top">${"%.2f" % p.price}</p>' if show_price else ""
            
            html += f"""
            <div>
                <div class="uk-card uk-card-default uk-card-small uk-card-hover">
                    <a href="/shop/product/{p.slug}" class="uk-link-reset">
                        <div class="uk-card-media-top">
                            {img}
                        </div>
                        <div class="uk-card-body uk-padding-small">
                            <h3 class="uk-card-title uk-text-small uk-margin-remove" style="min-height: 2.5em; overflow: hidden;">{p.name}</h3>
                            {price_html}
                        </div>
                    </a>
                    <div class="uk-card-body uk-padding-small uk-padding-remove-top">
                        <form action="/shop/cart/add/{p.id}" method="post" style="margin:0">
                            <input type="hidden" name="csrf_token" value="{csrf}"/>
                            <button type="submit" class="uk-button uk-button-primary uk-button-small uk-width-1-1">Add to Cart</button>
                        </form>
                    </div>
                </div>
            </div>
            """
        html += '</div>'
        return Markup(html)

    elif mod_type == "footer":
        logo_text = config.get("logo_text", "Devstack")
        description = process_shortcodes(config.get("description", ""))
        col1_title = config.get("col1_title", "")
        col1_html = process_shortcodes(config.get("col1_html", ""))
        col2_title = config.get("col2_title", "")
        col2_html = process_shortcodes(config.get("col2_html", ""))
        nl_title = config.get("newsletter_title", "")
        nl_text = process_shortcodes(config.get("newsletter_text", ""))
        copyright_txt = process_shortcodes(config.get("copyright", ""))
        twitter = config.get("twitter", "")
        github = config.get("github", "")
        discord = config.get("discord", "")

        html = '<div class="uk-margin-large-top">'
        
        # Top Grid
        html += '<div class="uk-grid-divider uk-child-width-1-2@s uk-child-width-1-4@m" uk-grid>'
        
        # Brand Col
        html += '<div>'
        if logo_text:
            html += f'<div class="uk-h3 devstack-gradient-text uk-margin-small-bottom">{logo_text}</div>'
        if description:
            html += f'<p class="uk-text-small uk-text-muted">{description}</p>'
        html += '</div>'
        
        # Col 1
        html += '<div>'
        if col1_title:
            html += f'<h4 class="uk-h5 uk-text-bold">{col1_title}</h4>'
        html += col1_html
        html += '</div>'
        
        # Col 2
        html += '<div>'
        if col2_title:
            html += f'<h4 class="uk-h5 uk-text-bold">{col2_title}</h4>'
        html += col2_html
        html += '</div>'
        
        # Newsletter
        html += '<div>'
        if nl_title:
            html += f'<h4 class="uk-h5 uk-text-bold">{nl_title}</h4>'
        if nl_text:
            html += f'<p class="uk-text-small uk-text-muted">{nl_text}</p>'
        html += '<form class="uk-form-stacked uk-margin-small-top" onsubmit="event.preventDefault();"><div class="uk-inline uk-width-1-1"><a class="uk-form-icon uk-form-icon-flip" href="#" uk-icon="icon: push"></a><input class="uk-input" type="email" placeholder="Email address..."></div></form>'
        html += '</div>'
        
        html += '</div>' # End Grid
        
        # Divider Line
        html += '<hr class="uk-margin-medium">'
        
        # Bottom Bar (Copyright & Socials)
        html += '<div class="uk-flex uk-flex-center uk-flex-middle uk-margin-bottom">'
        
        if twitter: html += f'<a href="{twitter}" class="uk-icon-button uk-margin-small-right" uk-icon="twitter"></a>'
        if github: html += f'<a href="{github}" class="uk-icon-button uk-margin-small-right" uk-icon="github"></a>'
        if discord: html += f'<a href="{discord}" class="uk-icon-button uk-margin-small-right" uk-icon="discord"></a>'
        
        html += '</div>'
        
        html += '<div class="uk-text-center">'
        if copyright_txt:
            html += f'<span class="uk-text-small uk-text-muted">{copyright_txt}</span>'
        html += '</div>'
        
        html += '</div>'
        
        return Markup(html)

    elif mod_type == "countdown":
        cd_date = config.get("date", "")
        if cd_date and len(cd_date) == 16:
            # HTML5 datetime-local outputs YYYY-MM-DDThh:mm. UIkit likes ISO 8601.
            cd_date += ":00+00:00"
            
        intro = process_shortcodes(config.get("intro", ""))
        outro = process_shortcodes(config.get("outro", ""))
        size = config.get("size", "default")
        labels = config.get("labels", False)
        separators = config.get("separators", False)
        
        countdown_html = f'<div class="uk-grid-small uk-child-width-auto uk-margin-small-top uk-flex-center" uk-grid uk-countdown="date: {cd_date}">'

        # Set text sizes
        num_size_class = ""
        sep_size_class = "uk-margin-small-left uk-margin-small-right"
        if size == "small":
            num_size_class = "uk-text-large" # Small heading
            sep_size_class += " uk-text-large"
        elif size == "large":
            num_size_class = "uk-heading-medium"
            sep_size_class += " uk-heading-medium"
        else:
            num_size_class = "uk-heading-small"
            sep_size_class += " uk-heading-small"

        def make_block(unit, label):
            lbl_html = f'<div class="uk-countdown-label uk-margin-small uk-text-center uk-visible@s">{label}</div>' if labels else ""
            return f'<div><div class="uk-countdown-number uk-countdown-{unit} {num_size_class}"></div>{lbl_html}</div>'

        sep_html = f'<div class="uk-countdown-separator {sep_size_class}">:</div>'

        countdown_html += make_block("days", "Days")
        if separators: countdown_html += sep_html
        countdown_html += make_block("hours", "Hours")
        if separators: countdown_html += sep_html
        countdown_html += make_block("minutes", "Minutes")
        if separators: countdown_html += sep_html
        countdown_html += make_block("seconds", "Seconds")
        
        countdown_html += '</div>'
        
        html = f'<div class="uk-text-center">'
        if intro:
            html += f'<div class="uk-margin-small-bottom">{intro}</div>'
            
        html += countdown_html
        
        if outro:
            # UIKit doesn't easily hide the timer automatically on expiration, 
            # so we'll render the outro as a permanent notice below the timer.
            html += f'<div class="uk-margin-small-top">{outro}</div>'
            
        html += f'</div>'
        
        return Markup(html)

    elif mod_type == "parallax":
        image_url = config.get("image", "")
        content = process_shortcodes(config.get("content", ""))
        height = config.get("height", "large")
        overlay_color = config.get("overlay_color", "#000000")
        overlay_opacity = config.get("overlay_opacity", "0.5")
        bg_effect = config.get("bg_effect", "bgy: -200")
        text_effect = config.get("text_effect", "opacity: 0,1; y: 100,0; viewport: 0.5")
        fixed = config.get("fixed", False)
        
        height_class = "uk-height-viewport" if height == "viewport" else f"uk-height-{height}"
        
        bg_style = f"background-image: url('{image_url}');" if image_url else ""
        if fixed:
            bg_attr = f'class="{height_class} uk-background-cover uk-background-fixed uk-light uk-flex uk-flex-center uk-flex-middle uk-position-relative" style="{bg_style}"'
        else:
            bg_attr = f'class="{height_class} uk-background-cover uk-light uk-flex uk-flex-center uk-flex-middle uk-position-relative" style="{bg_style}" uk-parallax="{bg_effect}"'
            
        overlay_style = f"background-color: {overlay_color}; opacity: {overlay_opacity}; position: absolute; inset: 0;"
        
        return Markup(
            f'<div {bg_attr}>'
            f'  <div style="{overlay_style}"></div>'
            f'  <div class="uk-position-relative uk-padding-large uk-text-center uk-width-1-1" uk-parallax="{text_effect}" style="z-index: 1;">'
            f'    {content}'
            f'  </div>'
            f'</div>'
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
        
        if height == "viewport":
            height_class = ""
            height_attr = 'uk-height-viewport="offset-top: true"'
        else:
            height_class = f"uk-height-{height}"
            height_attr = ""
            
        # Convert alignment to flex and text classes
        flex_align = "uk-flex-center" if align == "center" else ("uk-flex-right" if align == "right" else "")
        text_align = f"uk-text-{align}"
        
        parallax_attr = 'uk-parallax="bgsfx: 1.1,1; bgy: -100"' if parallax else ''
        shadow_style = "text-shadow: 2px 2px 8px rgba(0,0,0,0.8);" if text_shadow else ""
        
        btn_html = ""
        if btn_text and btn_url:
            btn_html = f'<div class="uk-margin-medium-top"><a href="{btn_url}" class="uk-button uk-button-{btn_style} uk-button-large">{btn_text}</a></div>'
            
        overlay_html = f'<div class="uk-position-cover" style="background-color: {overlay_color}; opacity: {overlay_opacity};"></div>'

        is_video = image_url.lower().endswith(('.mp4', '.webm', '.mov'))
        
        if is_video:
            bg_class = "uk-cover-container"
            bg_style = 'style="background-color: #1a1a1a;"'
            video_html = f'<video src="{image_url}" autoplay loop muted playsinline uk-cover></video>'
            img_attr = ""
        else:
            bg_class = "uk-background-cover uk-background-center-center"
            bg_style = f'style="background-image: url(\'{image_url}\'); background-color: #1a1a1a;"'
            video_html = ""
            img_attr = "uk-img"

        return Markup(
            f'<div class="{height_class} {bg_class} uk-light uk-flex {flex_align} uk-flex-middle uk-position-relative" '
            f'{height_attr} '
            f'{bg_style} '
            f'{parallax_attr if not is_video else ""} {img_attr}>'
            f'  {video_html}'
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

    elif mod_type == "breadcrumbs":
        from .models.cms import Page, Post
        path = request.path.strip("/")
        segments = path.split("/") if path else []
        
        # Build breadcrumb items
        items = [{"label": "Home", "url": "/"}]
        current_path = ""
        
        for i, seg in enumerate(segments):
            current_path += f"/{seg}"
            label = seg.replace("-", " ").replace("_", " ").capitalize()
            
            # Try to find a better title from DB
            # 1. Check Pages
            p = db.session.execute(db.select(Page).where(Page.slug == seg)).scalar_one_or_none()
            if p:
                label = p.title
            else:
                # 2. Check Posts (often prefixed with /blog/)
                if i > 0 and segments[i-1] == "blog":
                    post = db.session.execute(db.select(Post).where(Post.slug == seg)).scalar_one_or_none()
                    if post:
                        label = post.title
                elif seg == "blog":
                    label = "Blog"

            items.append({"label": label, "url": current_path})
            
        # Render UIkit breadcrumbs
        html = '<ul class="uk-breadcrumb">'
        for i, item in enumerate(items):
            if i == len(items) - 1:
                html += f'<li><span>{item["label"]}</span></li>'
            else:
                html += f'<li><a href="{item["url"]}">{item["label"]}</a></li>'
        html += '</ul>'
        
        return Markup(html)
        
    elif mod_type == "card":
        items = config.get("items", [])
        if not items:
            # Fallback for old single-card configs
            if "title" in config or "content" in config:
                items = [config]
                
        if len(items) == 1:
            return Markup(render_card(items[0]))
            
        grid_cols = config.get("grid_cols", "1-3")
        grid_gap = config.get("grid_gap", "medium")
        match_height = config.get("match_height", True)
        
        gap_class = f'uk-grid-{grid_gap}' if grid_gap != 'small' else 'uk-grid-small'
        if grid_gap == 'collapse':
            gap_class = 'uk-grid-collapse'
            
        match_attr = 'uk-height-match="target: > div > .uk-card"' if match_height else ''
        
        cards_html = ""
        for item in items:
            cards_html += f'<div>{render_card(item)}</div>'
            
        return Markup(
            f'<div class="{gap_class} uk-child-width-1-1 uk-child-width-{grid_cols}@m" uk-grid {match_attr}>'
            f'  {cards_html}'
            f'</div>'
        )
    elif mod_type == "accordion":
        items = config.get("items", [])
        collapsible = config.get("collapsible", True)
        multiple = config.get("multiple", False)
        duration = config.get("duration", 200)
        
        attr = f'uk-accordion="collapsible: {str(collapsible).lower()}; multiple: {str(multiple).lower()}; duration: {duration}"'
        html = f'<ul {attr}>'
        for item in items:
            title = item.get("title", "Untitled")
            content = process_shortcodes(item.get("content", ""))
            html += f'<li><a class="uk-accordion-title" href="#">{title}</a><div class="uk-accordion-content">{content}</div></li>'
        html += '</ul>'
        return Markup(html)

    elif mod_type == "slideshow":
        items = config.get("items", [])
        animation = config.get("animation", "slide")
        autoplay = config.get("autoplay", False)
        interval = config.get("interval", 3000)
        infinite = config.get("infinite", True)
        ratio = config.get("ratio", "16:9")
        min_height = config.get("min_height", 300)
        max_height = config.get("max_height", "")
        
        slideshow_opts = f'animation: {animation}; autoplay: {str(autoplay).lower()}; autoplay-interval: {interval}; infinite: {str(infinite).lower()}; ratio: {ratio};'
        if min_height: slideshow_opts += f' min-height: {min_height};'
        if max_height: slideshow_opts += f' max-height: {max_height};'
        
        items_html = ""
        for s in items:
            img = s.get("image") or ""
            title = s.get("title", "")
            caption = s.get("caption", "")
            
            overlay_html = ""
            if title or caption:
                overlay_html = (
                    f'<div class="uk-position-center uk-position-small uk-text-center uk-light">'
                    f'  <h2 class="uk-margin-remove" uk-slideshow-paralax="x: 100,-100">{title}</h2>'
                    f'  <p class="uk-margin-remove" uk-slideshow-paralax="x: 200,-200">{caption}</p>'
                    f'</div>'
                )
            
            items_html += (
                f'<li>'
                f'  <img src="{img}" alt="{title}" uk-cover>'
                f'  {overlay_html}'
                f'</li>'
            )
            
        html = (
            f'<div class="uk-position-relative uk-visible-toggle uk-light" tabindex="-1" uk-slideshow="{slideshow_opts}">'
            f'  <ul class="uk-slideshow-items">'
            f'    {items_html}'
            f'  </ul>'
            f'  <a class="uk-position-center-left uk-position-small uk-hidden-hover" href="#" uk-slidenav-previous uk-slideshow-item="previous"></a>'
            f'  <a class="uk-position-center-right uk-position-small uk-hidden-hover" href="#" uk-slidenav-next uk-slideshow-item="next"></a>'
            f'  <ul class="uk-slideshow-nav uk-dotnav uk-flex-center uk-margin"></ul>'
            f'</div>'
        )
        return Markup(html)

    return ""


def render_card(config: dict) -> str:
    """Render a UIkit Card based on configuration."""
    title = config.get("title", "")
    content = config.get("content", "")
    footer = config.get("footer", "")
    badge = config.get("badge", "")
    style = config.get("style", "default")
    size = config.get("size", "standard")
    image = config.get("image", "")
    image_pos = config.get("image_pos", "top")
    link = config.get("link", "")
    
    card_classes = ["uk-card", f"uk-card-{style}"]
    if size == "small":
        card_classes.append("uk-card-small")
    elif size == "large":
        card_classes.append("uk-card-large")
    if style == "hover":
        card_classes.append("uk-card-hover")
        
    card_class_str = " ".join(card_classes)
    
    image_html = ""
    if image:
        img_class = f"uk-card-media-{image_pos}"
        # Layouts for image
        if image_pos in ["left", "right"]:
            # Grid layout for side images
            grid_class = "uk-grid-collapse"
            if image_pos == "right":
                inner_grid = f'<div class="uk-width-expand uk-card-body">{title_html}{content}</div><div class="uk-width-1-3@m {img_class}"><img src="{image}" alt="{title}" class="uk-cover"></div>'
            else:
                inner_grid = f'<div class="uk-width-1-3@m {img_class}"><img src="{image}" alt="{title}" class="uk-cover"></div><div class="uk-width-expand uk-card-body">{title_html}{content}</div>'
            
            # (Incomplete logic, need better structure)
        else:
            image_html = f'<div class="{img_class}"><img src="{image}" alt="{title}"></div>'

    badge_html = f'<div class="uk-card-badge uk-label">{badge}</div>' if badge else ""
    title_html = f'<h3 class="uk-card-title">{title}</h3>' if title else ""
    footer_html = f'<div class="uk-card-footer">{footer}</div>' if footer else ""
    
    # Assembly
    if image and image_pos in ["left", "right"]:
        flex_class = "uk-flex-last@m" if image_pos == "right" else ""
        img_col = f'<div class="uk-width-1-3@m {img_class}"><div class="uk-cover-container" style="min-height: 200px;"><img src="{image}" alt="{title}" uk-cover></div></div>'
        body_col = f'<div class="uk-width-expand"><div class="uk-card-body">{badge_html}{title_html}{content}</div>{footer_html}</div>'
        
        main_content = f'<div class="uk-grid-collapse uk-child-width-expand@s" uk-grid>'
        if image_pos == "right":
             main_content += f'{body_col}{img_col}'
        else:
             main_content += f'{img_col}{body_col}'
        main_content += '</div>'
    else:
        # standard top/bottom
        main_content = ""
        if image and image_pos == "top":
            main_content += image_html
        
        main_content += f'<div class="uk-card-body">{badge_html}{title_html}{content}</div>'
        
        if image and image_pos == "bottom":
            main_content += image_html
            
        if footer:
            main_content += footer_html

    base_html = f'<div class="{card_class_str}">{main_content}</div>'
    
    if link:
        return f'<a href="{link}" class="uk-link-reset">{base_html}</a>'
    return base_html


def process_shortcodes(text: str | None) -> str:
    """Parse [tag attr="val"]content[/tag] shortcodes."""
    if not text:
        return ""
        
    pattern = re.compile(r'\[(\w+)([^\]]*?)\](?:(.*?)\[/\1\])?', re.DOTALL)
    
    def replacement(match):
        tag = match.group(1)
        attrs_str = match.group(2)
        content = match.group(3) or ""
        
        # Parse attributes (e.g. key="value")
        attrs = {}
        attr_pattern = re.compile(r'(\w+)="([^"]*)"')
        for k, v in attr_pattern.findall(attrs_str):
            attrs[k] = v
            
        if tag == "card":
            if content:
                attrs["content"] = content
            return render_card(attrs)
            
        return match.group(0) # Keep unknown tags as is
        
    return pattern.sub(replacement, text)


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
            
        # Ensure position_widths exists and behaves gracefully for templates
        if "position_widths" not in config:
            config["position_widths"] = {}
            
        # Use a wrapper to avoid KeyErrors in templates
        class SafeConfig(dict):
            def __getitem__(self, key):
                return super().get(key, "default")

        if isinstance(config.get("position_widths"), dict):
            config["position_widths"] = SafeConfig(config["position_widths"])
            
        return {
            "render_position": lambda pos, default="": Markup(render_position(pos, default)),
            "get_positions": get_positions,
            "get_layouts": get_layouts,
            "theme_config": config,
            "active_theme": settings.active_theme,
            "site_settings": settings
        }

    # Also make render_position available as a global
    app.jinja_env.globals["render_position"] = lambda pos, default="": Markup(render_position(pos, default))
    
    # Register shortcode filter
    app.jinja_env.filters["shortcodes"] = lambda text: Markup(process_shortcodes(text))
    app.jinja_env.filters["from_json"] = from_json_filter
    app.jinja_env.filters["slugify"] = slugify_filter


def get_main_menu_items(menu_id: Optional[int] = None) -> list[dict]:
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
