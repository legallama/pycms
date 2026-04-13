from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from datetime import datetime, timedelta, timezone
from sqlalchemy import func

from ..extensions import db
from ..models.user import User
from ..auth import require_roles
from ..models.user import UserRole
from ..models.cms import Page, Post
from ..models.shop import Order
from ..models.crm import Lead
from ..utils.ai_helper import AIHelper
from .forms import LoginForm, UserCreateForm, UserEditForm

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
    
    return render_template("admin/dashboard.html", 
                           seo_warnings=seo_warnings,
                           top_content=top_content,
                           order_labels=order_labels,
                           order_values=order_values,
                           leads_today=leads_today)


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

