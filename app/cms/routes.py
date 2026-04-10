from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..auth import require_roles
from ..extensions import db
from ..models.cms import Page, Post, PublishStatus
from ..models.navigation import Menu
from ..models.user import UserRole
from .forms import PageForm, PostForm
from ..templating import get_layouts

cms_bp = Blueprint("cms", __name__, template_folder="../templates")


def _can_edit_content(owner_id: int) -> bool:
    role = current_user.get_role()
    if role in (UserRole.ADMIN.value, UserRole.EDITOR.value):
        return True
    return role == UserRole.AUTHOR.value and current_user.id == owner_id


@cms_bp.get("/pages")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def pages_list():
    status = request.args.get("status", "").strip().lower()
    qtxt = request.args.get("q", "").strip()

    q = db.select(Page)
    if status in (PublishStatus.DRAFT.value, PublishStatus.PUBLISHED.value):
        q = q.where(Page.status == status)
    if qtxt:
        q = q.where(Page.title.ilike(f"%{qtxt}%"))
    q = q.order_by(Page.updated_at.desc())
    pages = db.session.execute(q).scalars().all()
    return render_template("admin/pages/list.html", pages=pages, status=status, q=qtxt)


@cms_bp.route("/pages/new", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def pages_new():
    form = PageForm()
    layouts = get_layouts()
    form.layout.choices = [(l, cfg["label"]) for l, cfg in layouts.items()]
    
    menus = db.session.execute(db.select(Menu).order_by(Menu.name.asc())).scalars().all()
    form.menu_id.choices = [(0, "Default (Main Menu)")] + [(m.id, m.name) for m in menus]
    
    if current_user.get_role() == UserRole.AUTHOR.value:
        form.status.data = PublishStatus.DRAFT.value

    if form.validate_on_submit():
        slug = form.slug.data.strip().strip("/")
        existing = db.session.execute(db.select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if existing:
            flash("Slug already exists.", "danger")
        else:
            status = form.status.data
            if current_user.get_role() == UserRole.AUTHOR.value:
                status = PublishStatus.DRAFT.value
            page = Page(
                title=form.title.data.strip(),
                slug=slug,
                body_html=form.body_html.data or "",
                status=status,
                layout=form.layout.data or "default",
                menu_id=(form.menu_id.data if form.menu_id.data > 0 else None),
                published_at=(datetime.now(timezone.utc) if status == PublishStatus.PUBLISHED.value else None),
                created_by_id=current_user.id,
                updated_at=datetime.now(timezone.utc),
            )
            db.session.add(page)
            db.session.commit()
            flash("Page created.", "success")
            return redirect(url_for("cms.pages_list"))

    return render_template("admin/pages/edit.html", form=form, page=None)


@cms_bp.route("/pages/<int:page_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def pages_edit(page_id: int):
    page = db.session.get(Page, page_id)
    if not page:
        return ("Not Found", 404)
    if not _can_edit_content(page.created_by_id):
        return ("Forbidden", 403)

    form = PageForm(obj=page)
    layouts = get_layouts()
    form.layout.choices = [(l, cfg["label"]) for l, cfg in layouts.items()]

    menus = db.session.execute(db.select(Menu).order_by(Menu.name.asc())).scalars().all()
    form.menu_id.choices = [(0, "Default (Main Menu)")] + [(m.id, m.name) for m in menus]
    if not form.is_submitted():
        form.menu_id.data = page.menu_id or 0

    if current_user.get_role() == UserRole.AUTHOR.value:
        form.status.data = PublishStatus.DRAFT.value

    if form.validate_on_submit():
        slug = form.slug.data.strip().strip("/")
        existing = db.session.execute(db.select(Page).where(Page.slug == slug, Page.id != page.id)).scalar_one_or_none()
        if existing:
            flash("Slug already exists.", "danger")
        else:
            page.title = form.title.data.strip()
            page.slug = slug
            page.body_html = form.body_html.data or ""
            page.layout = form.layout.data or "default"
            page.menu_id = (form.menu_id.data if form.menu_id.data > 0 else None)
            if current_user.get_role() in (UserRole.ADMIN.value, UserRole.EDITOR.value):
                page.status = form.status.data
                page.published_at = (
                    datetime.now(timezone.utc) if page.status == PublishStatus.PUBLISHED.value else None
                )
            page.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            flash("Page updated.", "success")
            return redirect(url_for("cms.pages_list"))

    return render_template("admin/pages/edit.html", form=form, page=page)


@cms_bp.get("/posts")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def posts_list():
    status = request.args.get("status", "").strip().lower()
    qtxt = request.args.get("q", "").strip()

    q = db.select(Post)
    if status in (PublishStatus.DRAFT.value, PublishStatus.PUBLISHED.value):
        q = q.where(Post.status == status)
    if qtxt:
        q = q.where(Post.title.ilike(f"%{qtxt}%"))
    q = q.order_by(Post.updated_at.desc())
    posts = db.session.execute(q).scalars().all()
    return render_template("admin/posts/list.html", posts=posts, status=status, q=qtxt)


@cms_bp.route("/posts/new", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def posts_new():
    form = PostForm()
    if current_user.get_role() == UserRole.AUTHOR.value:
        form.status.data = PublishStatus.DRAFT.value

    if form.validate_on_submit():
        slug = form.slug.data.strip().strip("/")
        existing = db.session.execute(db.select(Post).where(Post.slug == slug)).scalar_one_or_none()
        if existing:
            flash("Slug already exists.", "danger")
        else:
            status = form.status.data
            if current_user.get_role() == UserRole.AUTHOR.value:
                status = PublishStatus.DRAFT.value
            post = Post(
                title=form.title.data.strip(),
                slug=slug,
                body_html=form.body_html.data or "",
                status=status,
                published_at=(datetime.now(timezone.utc) if status == PublishStatus.PUBLISHED.value else None),
                created_by_id=current_user.id,
                updated_at=datetime.now(timezone.utc),
            )
            db.session.add(post)
            db.session.commit()
            flash("Post created.", "success")
            return redirect(url_for("cms.posts_list"))

    return render_template("admin/posts/edit.html", form=form, post=None)


@cms_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def posts_edit(post_id: int):
    post = db.session.get(Post, post_id)
    if not post:
        return ("Not Found", 404)
    if not _can_edit_content(post.created_by_id):
        return ("Forbidden", 403)

    form = PostForm(obj=post)
    if current_user.get_role() == UserRole.AUTHOR.value:
        form.status.data = PublishStatus.DRAFT.value

    if form.validate_on_submit():
        slug = form.slug.data.strip().strip("/")
        existing = db.session.execute(db.select(Post).where(Post.slug == slug, Post.id != post.id)).scalar_one_or_none()
        if existing:
            flash("Slug already exists.", "danger")
        else:
            post.title = form.title.data.strip()
            post.slug = slug
            post.body_html = form.body_html.data or ""
            if current_user.get_role() in (UserRole.ADMIN.value, UserRole.EDITOR.value):
                post.status = form.status.data
                post.published_at = (
                    datetime.now(timezone.utc) if post.status == PublishStatus.PUBLISHED.value else None
                )
            post.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            flash("Post updated.", "success")
            return redirect(url_for("cms.posts_list"))

    return render_template("admin/posts/edit.html", form=form, post=post)

