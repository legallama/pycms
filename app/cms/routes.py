from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..auth import require_roles
from ..extensions import db
from ..models.cms import Page, Post, PublishStatus, Revision
from ..models.navigation import Menu
from ..models.user import UserRole
from .forms import PageForm, PostForm
from ..templating import get_layouts
from ..utils.audit import log_action, save_revision, PreviewHelper

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
                meta_description=form.meta_description.data,
                meta_keywords=form.meta_keywords.data,
            )
            db.session.add(page)
            db.session.commit()
            save_revision(page, note="Initial creation")
            log_action("Page Created", details=f"Title: {page.title}", target_type="page", target_id=page.id)
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
            page.meta_description = form.meta_description.data
            page.meta_keywords = form.meta_keywords.data
            db.session.commit()
            save_revision(page, note=request.form.get("revision_note", "Regular update"))
            log_action("Page Updated", details=f"Title: {page.title}", target_type="page", target_id=page.id)
            flash("Page updated.", "success")
            return redirect(url_for("cms.pages_list"))

    preview_token = PreviewHelper.generate_token("page", page.id)
    revisions = db.session.execute(
        db.select(Revision).where(Revision.target_type == "page", Revision.target_id == page.id).order_by(Revision.created_at.desc())
    ).scalars().all()
    return render_template("admin/pages/edit.html", form=form, page=page, preview_token=preview_token, revisions=revisions)


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
                meta_description=form.meta_description.data,
                meta_keywords=form.meta_keywords.data,
            )
            db.session.add(post)
            db.session.commit()
            save_revision(post, note="Initial creation")
            log_action("Post Created", details=f"Title: {post.title}", target_type="post", target_id=post.id)
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
            post.meta_description = form.meta_description.data
            post.meta_keywords = form.meta_keywords.data
            db.session.commit()
            save_revision(post, note=request.form.get("revision_note", "Regular update"))
            log_action("Post Updated", details=f"Title: {post.title}", target_type="post", target_id=post.id)
            flash("Post updated.", "success")
            return redirect(url_for("cms.posts_list"))

    preview_token = PreviewHelper.generate_token("post", post.id)
    revisions = db.session.execute(
        db.select(Revision).where(Revision.target_type == "post", Revision.target_id == post.id).order_by(Revision.created_at.desc())
    ).scalars().all()
    return render_template("admin/posts/edit.html", form=form, post=post, preview_token=preview_token, revisions=revisions)


@cms_bp.post("/revisions/<int:rev_id>/restore")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def revision_restore(rev_id: int):
    from ..models.cms import Revision
    rev = db.session.get(Revision, rev_id)
    if not rev: abort(404)
    
    import json
    data = json.loads(rev.data_json)
    
    if rev.target_type == "page":
        obj = db.session.get(Page, rev.target_id)
    else:
        obj = db.session.get(Post, rev.target_id)
        
    if not obj: abort(404)
    
    # Restore fields
    for key, val in data.items():
        if hasattr(obj, key) and key not in ("id", "created_at", "updated_at"):
            # Handle datetime strings if any
            if key == "published_at" and val:
                val = datetime.fromisoformat(val)
            setattr(obj, key, val)
    
    db.session.commit()
    log_action("Revision Restored", details=f"Restored to revision from {rev.created_at}", target_type=rev.target_type, target_id=obj.id)
    save_revision(obj, note=f"Restored from version {rev.id}")
    
    flash(f"Restored to version from {rev.created_at.strftime('%b %d, %H:%M')}", "success")
    if rev.target_type == "page":
        return redirect(url_for('cms.pages_edit', page_id=obj.id))
    return redirect(url_for('cms.posts_edit', post_id=obj.id))

