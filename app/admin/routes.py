from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import current_user, login_required, login_user, logout_user
from datetime import datetime, timedelta, timezone
from sqlalchemy import func

from ..extensions import db
from ..models.user import User
from ..auth import require_roles
from ..models.user import UserRole
from ..models.cms import Page, Post
from ..models.navigation import Module
from ..models.shop import Order
from ..models.crm import Lead
from ..utils.ai_helper import AIHelper
from .forms import LoginForm, UserCreateForm, UserEditForm

from ..utils.audit import log_action, save_revision, PreviewHelper

admin_bp = Blueprint("admin", __name__, template_folder="../templates")


@admin_bp.get("/")
@login_required
def dashboard():
    from ..site.routes import get_seo_warnings
    seo_warnings = get_seo_warnings()
    
    # 1. Top Performing Pages
    pages = db.session.execute(db.select(Page).order_by(Page.views.desc()).limit(5)).scalars().all()
    posts = db.session.execute(db.select(Post).order_by(Post.views.desc()).limit(5)).scalars().all()
    top_content = sorted(list(pages) + list(posts), key=lambda x: x.views, reverse=True)[:5]
    
    # 2. Recent Orders Value (Last 7 Days)
    today = datetime.now(timezone.utc).date()
    week_ago = today - timedelta(days=6)
    
    daily_orders = db.session.execute(
        db.select(func.date(Order.created_at), func.sum(Order.total_amount))
        .where(Order.created_at >= week_ago)
        .group_by(func.date(Order.created_at))
    ).all()
    
    order_labels = []
    order_values = []
    map_orders = {str(d): val for d, val in daily_orders}
    for i in range(7):
        d = week_ago + timedelta(days=i)
        ds = str(d)
        order_labels.append(d.strftime("%b %d"))
        order_values.append(float(map_orders.get(ds, 0)))

    # 3. Leads Today
    leads_today = db.session.execute(
       db.select(func.count(Lead.id)).where(func.date(Lead.created_at) == today)
    ).scalar() or 0
    
    # 4. Activity Stream
    from ..models.cms import AuditLog
    activity = db.session.execute(
        db.select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10)
    ).scalars().all()
    
    return render_template("admin/dashboard.html", 
                           seo_warnings=seo_warnings,
                           top_content=top_content,
                           order_labels=order_labels,
                           order_values=order_values,
                           leads_today=leads_today,
                           activity=activity)


@admin_bp.get("/users")
@login_required
@require_roles(UserRole.ADMIN)
def users_list():
    users = db.session.execute(db.select(User).order_by(User.created_at.desc())).scalars().all()
    return render_template("admin/users/list.html", users=users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN)
def users_new():
    form = UserCreateForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        existing = db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            flash("Email already exists.", "danger")
        else:
            user = User(email=email, role=form.role.data, is_active=bool(form.is_active.data))
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash("User created.", "success")
            return redirect(url_for("admin.users_list"))
    return render_template("admin/users/new.html", form=form)


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN)
def users_edit(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        return ("Not Found", 404)

    form = UserEditForm(obj=user)
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        existing = db.session.execute(
            db.select(User).where(User.email == email, User.id != user.id)
        ).scalar_one_or_none()
        if existing:
            flash("Email already exists.", "danger")
        else:
            user.email = email
            user.role = form.role.data
            user.is_active = bool(form.is_active.data)
            if form.password.data:
                user.set_password(form.password.data)
            db.session.commit()
            flash("User updated.", "success")
            return redirect(url_for("admin.users_list"))

    return render_template("admin/users/edit.html", form=form, user=user)


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none()
        if not user or not user.is_active or not user.check_password(form.password.data):
            flash("Invalid credentials.", "danger")
        else:
            login_user(user, remember=True)
            next_url = request.args.get("next")
            return redirect(next_url or url_for("admin.dashboard"))

    return render_template("admin/login.html", form=form)


@admin_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))

@admin_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name")
        current_user.bio = request.form.get("bio")
        current_user.profile_photo_url = request.form.get("profile_photo_url")
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("admin.profile"))
    return render_template("admin/profile.html")


@admin_bp.post("/ai/process")
@login_required
def ai_process():
    data = request.get_json() or {}
    action = data.get("action")
    input_text = data.get("text", "")
    
    if action == "generate":
        prompt = f"Write a complete, educational, and engaging blog post about: {input_text}. Use HTML for formatting (h2, p, ul)."
        res = AIHelper.generate_content(prompt)
    elif action == "seo":
        res = AIHelper.get_seo_suggestions(input_text)
    elif action == "rewrite":
        mode = data.get("mode", "professional")
        res = AIHelper.rewrite_text(input_text, mode)
    else:
        return {"error": "Invalid action"}, 400
        
    return {"result": res}
@admin_bp.get("/visual-editor")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def visual_editor_list():
    pages = db.session.execute(db.select(Page).order_by(Page.title.asc())).scalars().all()
    return render_template("admin/editor/list.html", pages=pages)


@admin_bp.get("/visual-editor/<int:page_id>")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def visual_editor(page_id: int):
    from ..models.constants import MODULE_TYPES
    page = db.session.get(Page, page_id)
    if not page:
        return ("Not Found", 404)
    return render_template("admin/editor/visual.html", page=page, module_types=MODULE_TYPES)


@admin_bp.post("/api/blocks/reorder")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def api_reorder_block():
    data = request.get_json() or {}
    block_id = data.get("block_id")
    new_position = data.get("position")
    new_order = data.get("order")
    
    from ..models.navigation import Module
    block = db.session.get(Module, block_id)
    if not block:
        return {"error": "Block not found"}, 404
        
    # Simple reordering logic
    # Move others in the same position
    siblings = db.session.execute(
        db.select(Module).where(Module.position == new_position, Module.id != block.id).order_by(Module.order.asc())
    ).scalars().all()
    
    block.position = new_position
    block.order = new_order
    
    current_o = 0
    for s in siblings:
        if current_o == new_order:
            current_o += 1
        s.order = current_o
        current_o += 1
        
    db.session.commit()
    return {"status": "ok"}


@admin_bp.post("/api/blocks/create")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def api_create_block():
    data = request.json
    page_id = data.get("page_id")
    block_type = data.get("type")
    position = data.get("position")
    index = data.get("index", 0)
    
    # 1. Create the module
    m = Module(
        title=f"New {block_type.capitalize()}",
        type=block_type,
        enabled=True,
        config_json="{}",
        position=position,
        order=index
    )
    db.session.add(m)
    db.session.flush() # Get ID
    
    # 2. Shift others in the same position
    others = db.session.execute(
        db.select(Module).where(Module.id != m.id, Module.position == position).order_by(Module.order)
    ).scalars().all()
    
    for other in others:
        if other.order >= index:
            other.order = other.order + 1
            
    db.session.commit()
    return jsonify({"success": True, "module_id": m.id})
