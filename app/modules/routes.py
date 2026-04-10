from __future__ import annotations

import json

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..auth import require_roles
from ..extensions import db
from ..models.navigation import Module, Menu, MenuItem
from ..models.user import UserRole
from ..models.constants import MODULE_TYPES
from ..templating import get_positions, get_main_menu_items

modules_bp = Blueprint("modules", __name__, template_folder="../templates")


@modules_bp.get("/modules")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def modules_list():
    mods = db.session.execute(db.select(Module).order_by(Module.position.asc(), Module.order.asc())).scalars().all()
    positions = get_positions()
    return render_template("admin/modules/list.html", mods=mods, positions=positions)


@modules_bp.route("/modules/new", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def modules_new():
    from ..models.constants import MODULE_TYPES
    positions = get_positions()
    
    menus = db.session.execute(db.select(Menu).order_by(Menu.name.asc())).scalars().all()
    menu_items = db.session.execute(db.select(MenuItem).order_by(MenuItem.menu_id.asc(), MenuItem.order.asc())).scalars().all()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        position = (request.form.get("position") or "header").strip()
        m_type = request.form.get("type") or "html"
        enabled = bool(request.form.get("enabled"))
        show_title = bool(request.form.get("show_title"))
        css_class = (request.form.get("css_class") or "").strip()
        
        # Build config based on type
        config = {"show_title": show_title}
        if m_type == "html":
            config["html"] = request.form.get("html") or ""
        elif m_type == "text":
            config["text"] = request.form.get("text") or ""
        elif m_type == "menu":
            config["menu_name"] = request.form.get("menu_name") or "main"
        elif m_type == "recent_posts":
            config["count"] = int(request.form.get("count") or 5)
        elif m_type == "hero":
            config["image_url"] = request.form.get("image_url") or ""
            config["title"] = request.form.get("hero_title") or ""
            config["subtitle"] = request.form.get("hero_subtitle") or ""
            config["height"] = request.form.get("height") or "viewport"
            config["overlay_color"] = request.form.get("overlay_color") or "#000000"
            config["overlay_opacity"] = float(request.form.get("overlay_opacity") or 0.4)
            config["align"] = request.form.get("align") or "center"
            config["btn_text"] = request.form.get("btn_text") or ""
            config["btn_url"] = request.form.get("btn_url") or ""
            config["btn_style"] = request.form.get("btn_style") or "primary"
            config["text_shadow"] = bool(request.form.get("text_shadow"))
            config["parallax"] = bool(request.form.get("parallax"))
        elif m_type == "slider":
            config["autoplay"] = bool(request.form.get("autoplay"))
            config["interval"] = int(request.form.get("interval") or 3000)
            config["infinite"] = bool(request.form.get("infinite", True))
            config["center"] = bool(request.form.get("center"))
            config["nav_arrows"] = bool(request.form.get("nav_arrows", True))
            config["nav_dots"] = bool(request.form.get("nav_dots", True))
            
            imgs = request.form.getlist("slide_img[]")
            titles = request.form.getlist("slide_title[]")
            urls = request.form.getlist("slide_url[]")
            
            slides = []
            for i in range(len(imgs)):
                if imgs[i]:
                    slides.append({
                        "image": imgs[i],
                        "title": titles[i] if i < len(titles) else "",
                        "url": urls[i] if i < len(urls) else "#"
                    })
            config["slides"] = slides

        if not title:
            flash("Title is required.", "danger")
        elif position not in positions:
            flash("Invalid position.", "danger")
        else:
            max_order = (
                db.session.execute(db.select(db.func.max(Module.order)).where(Module.position == position)).scalar() or 0
            )
            m = Module(
                title=title,
                position=position,
                type=m_type,
                config_json=json.dumps(config),
                enabled=enabled,
                order=max_order + 1,
                show_title=show_title,
                css_class=css_class,
                assignment_type=request.form.get("assignment_type", "all")
            )
            
            if m.assignment_type == "selected":
                item_ids = request.form.getlist("assigned_items", type=int)
                items = db.session.execute(db.select(MenuItem).where(MenuItem.id.in_(item_ids))).scalars().all()
                m.assigned_items = items
            
            db.session.add(m)
            db.session.commit()
            flash("Module created.", "success")
            return redirect(url_for("modules.modules_list"))

    return render_template(
        "admin/modules/edit.html", 
        module=None, 
        positions=positions, 
        module_types=MODULE_TYPES,
        menus=menus,
        menu_items=menu_items
    )


@modules_bp.route("/modules/<int:module_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def modules_edit(module_id: int):
    from ..models.constants import MODULE_TYPES
    m = db.session.get(Module, module_id)
    if not m:
        return ("Not Found", 404)

    positions = get_positions()
    cfg = {}
    try:
        cfg = json.loads(m.config_json or "{}")
    except json.JSONDecodeError:
        cfg = {}

    menus = db.session.execute(db.select(Menu).order_by(Menu.name.asc())).scalars().all()
    menu_items = db.session.execute(db.select(MenuItem).order_by(MenuItem.menu_id.asc(), MenuItem.order.asc())).scalars().all()

    if request.method == "POST":
        m.title = (request.form.get("title") or "").strip()
        m.position = (request.form.get("position") or "header").strip()
        m.type = request.form.get("type") or "html"
        m.enabled = bool(request.form.get("enabled"))
        m.show_title = bool(request.form.get("show_title"))
        m.css_class = (request.form.get("css_class") or "").strip()
        m.assignment_type = request.form.get("assignment_type", "all")

        # Update config based on type
        cfg["show_title"] = m.show_title
        if m.type == "html":
            cfg["html"] = request.form.get("html") or ""
        elif m.type == "text":
            cfg["text"] = request.form.get("text") or ""
        elif m.type == "menu":
            cfg["menu_name"] = request.form.get("menu_name") or "main"
            cfg["dropdown_width"] = request.form.get("dropdown_width") or "standard"
        elif m.type == "recent_posts":
            cfg["count"] = int(request.form.get("count") or 5)
        elif m.type == "hero":
            cfg["image_url"] = request.form.get("image_url") or ""
            cfg["title"] = request.form.get("hero_title") or ""
            cfg["subtitle"] = request.form.get("hero_subtitle") or ""
            cfg["height"] = request.form.get("height") or "viewport"
            cfg["overlay_color"] = request.form.get("overlay_color") or "#000000"
            cfg["overlay_opacity"] = float(request.form.get("overlay_opacity") or 0.4)
            cfg["align"] = request.form.get("align") or "center"
            cfg["btn_text"] = request.form.get("btn_text") or ""
            cfg["btn_url"] = request.form.get("btn_url") or ""
            cfg["btn_style"] = request.form.get("btn_style") or "primary"
            cfg["text_shadow"] = bool(request.form.get("text_shadow"))
            cfg["parallax"] = bool(request.form.get("parallax"))
        elif m.type == "slider":
            cfg["autoplay"] = bool(request.form.get("autoplay"))
            cfg["interval"] = int(request.form.get("interval") or 3000)
            cfg["infinite"] = bool(request.form.get("infinite", True))
            cfg["center"] = bool(request.form.get("center"))
            cfg["nav_arrows"] = bool(request.form.get("nav_arrows", True))
            cfg["nav_dots"] = bool(request.form.get("nav_dots", True))
            
            # Process slides
            imgs = request.form.getlist("slide_img[]")
            titles = request.form.getlist("slide_title[]")
            urls = request.form.getlist("slide_url[]")
            
            slides = []
            for i in range(len(imgs)):
                if imgs[i]:
                    slides.append({
                        "image": imgs[i],
                        "title": titles[i] if i < len(titles) else "",
                        "url": urls[i] if i < len(urls) else "#"
                    })
            cfg["slides"] = slides
        elif m.type == "gallery":
            cfg["grid_cols"] = request.form.get("grid_cols") or "1-3"
            cfg["grid_gap"] = request.form.get("grid_gap") or "small"
            cfg["lightbox"] = bool(request.form.get("lightbox"))
            cfg["masonry"] = bool(request.form.get("masonry"))
            
            # Process items
            imgs = request.form.getlist("gallery_img[]")
            captions = request.form.getlist("gallery_caption[]")
            
            items = []
            for i in range(len(imgs)):
                if imgs[i]:
                    items.append({
                        "image": imgs[i],
                        "caption": captions[i] if i < len(captions) else ""
                    })
            cfg["items"] = items
        elif m.type == "media_lightbox":
            cfg["grid_cols"] = request.form.get("grid_cols") or "1-3"
            cfg["grid_gap"] = request.form.get("grid_gap") or "medium"
            
            # Process items
            m_types = request.form.getlist("m_type[]")
            urls = request.form.getlist("m_url[]")
            thumbs = request.form.getlist("m_thumb[]")
            captions = request.form.getlist("m_caption[]")
            
            items = []
            for i in range(len(urls)):
                if urls[i]:
                    items.append({
                        "type": m_types[i] if i < len(m_types) else "image",
                        "url": urls[i],
                        "thumb": thumbs[i] if i < len(thumbs) else "",
                        "caption": captions[i] if i < len(captions) else ""
                    })
            cfg["items"] = items

        if not m.title:
            flash("Title is required.", "danger")
        elif m.position not in positions:
            flash("Invalid position.", "danger")
        else:
            # Handle item assignments
            if m.assignment_type == "selected":
                item_ids = request.form.getlist("assigned_items", type=int)
                items = db.session.execute(db.select(MenuItem).where(MenuItem.id.in_(item_ids))).scalars().all()
                m.assigned_items = items
            else:
                m.assigned_items = []

            m.config_json = json.dumps(cfg)
            db.session.commit()
            flash("Module updated.", "success")
            return redirect(url_for("modules.modules_list"))

    return render_template(
        "admin/modules/edit.html",
        module=m,
        positions=positions,
        module_types=MODULE_TYPES,
        config=cfg,
        menus=menus,
        menu_items=menu_items
    )


@modules_bp.post("/modules/<int:module_id>/delete")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def modules_delete(module_id: int):
    m = db.session.get(Module, module_id)
    if not m:
        return ("Not Found", 404)
    db.session.delete(m)
    db.session.commit()
    flash("Module deleted.", "success")
    return redirect(url_for("modules.modules_list"))
