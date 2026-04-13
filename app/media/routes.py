from __future__ import annotations

import os
import secrets
import base64
import io
from pathlib import Path

from typing import Optional

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import login_required
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..auth import require_roles
from ..extensions import db
from ..models.media import MediaFile, MediaFolder
from ..models.user import UserRole

media_bp = Blueprint("media", __name__, template_folder="../templates")

ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ALLOWED_OTHER_EXTS = {".pdf", ".mp4", ".mov", ".webm"}
ALLOWED_EXTS = ALLOWED_IMAGE_EXTS | ALLOWED_OTHER_EXTS
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _format_size(size_bytes: int) -> str:
    """Convert byte count to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


@media_bp.app_context_processor
def _inject_media_helpers():
    return {"format_size": _format_size}


def _uploads_root() -> Path:
    p = Path(current_app.config["UPLOAD_DIR"])
    return p


def _ensure_dirs() -> tuple[Path, Path]:
    root = _uploads_root()
    originals = root / "originals"
    thumbs = root / "thumbs"
    originals.mkdir(parents=True, exist_ok=True)
    thumbs.mkdir(parents=True, exist_ok=True)
    return originals, thumbs


def _ext(filename: str) -> str:
    return Path(filename).suffix.lower()


def _save_upload(fs: FileStorage) -> tuple[str, str, int, Optional[int], Optional[int]]:
    if not fs or not fs.filename:
        raise ValueError("Missing file")
    filename = secure_filename(fs.filename)
    if not filename:
        raise ValueError("Invalid filename")

    ext = _ext(filename)
    if ext not in ALLOWED_EXTS:
        raise ValueError("File type not allowed")

    fs.stream.seek(0, os.SEEK_END)
    size = fs.stream.tell()
    fs.stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise ValueError("File too large")

    originals, thumbs = _ensure_dirs()
    token = secrets.token_hex(12)
    
    is_image = ext in ALLOWED_IMAGE_EXTS
    target_ext = ".webp" if (is_image and ext != ".gif") else ext
    stored_name = f"{token}{target_ext}"
    stored_rel = f"originals/{stored_name}"
    stored_path = originals / stored_name

    width = height = None
    if is_image and ext != ".gif":
        # Convert to WebP
        with Image.open(fs.stream) as im:
            width, height = im.size
            im.save(stored_path, "WEBP", quality=85)
            
            # Save thumbnail as WebP too
            im.thumbnail((400, 400))
            thumb_path = thumbs / stored_name
            im.save(thumb_path, "WEBP")
        mime = "image/webp"
    else:
        # Save as original
        fs.save(stored_path)
        mime = fs.mimetype or "application/octet-stream"
        if ext == ".gif":
            with Image.open(stored_path) as im:
                width, height = im.size
                im.thumbnail((400, 400))
                thumb_path = thumbs / stored_name
                im.save(thumb_path)

    return stored_rel, filename, size, width, height, mime


@media_bp.get("/media")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def media_list():
    folder_id = request.args.get("folder_id", type=int)
    mode = request.args.get("mode")
    
    # Breadcrumbs logic
    breadcrumbs = []
    current_folder = None
    if folder_id:
        current_folder = db.session.get(MediaFolder, folder_id)
        temp = current_folder
        while temp:
            breadcrumbs.insert(0, temp)
            temp = db.session.get(MediaFolder, temp.parent_id) if temp.parent_id else None

    # Fetch folders and files in current location
    folders = db.session.execute(db.select(MediaFolder).where(MediaFolder.parent_id == folder_id).order_by(MediaFolder.name.asc())).scalars().all()
    files = db.session.execute(db.select(MediaFile).where(MediaFile.folder_id == folder_id).order_by(MediaFile.created_at.desc())).scalars().all()
    
    # All folders for "Move" modal
    folders_all = db.session.execute(db.select(MediaFolder).order_by(MediaFolder.name.asc())).scalars().all()
    
    return render_template("admin/media/list.html", files=files, folders=folders, folders_all=folders_all, breadcrumbs=breadcrumbs, current_folder=current_folder, mode=mode)


@media_bp.post("/media/folders/new")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def media_folder_new():
    name = request.form.get("name", "New Folder")
    parent_id = request.form.get("parent_id", type=int)
    f = MediaFolder(name=name, parent_id=parent_id)
    db.session.add(f)
    db.session.commit()
    return redirect(url_for("media.media_list", folder_id=parent_id))


@media_bp.post("/media/files/<int:file_id>/move")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def media_file_move(file_id: int):
    target_folder_id = request.form.get("folder_id", type=int)
    mf = db.session.get(MediaFile, file_id)
    if mf:
        mf.folder_id = target_folder_id
        db.session.commit()
    return redirect(url_for("media.media_list", folder_id=target_folder_id))


@media_bp.post("/media/upload")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def media_upload():
    fs = request.files.get("file")
    folder_id = request.form.get("folder_id", type=int)
    try:
        rel_path, original_name, size, width, height, mime = _save_upload(fs)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("media.media_list", folder_id=folder_id))

    mf = MediaFile(path=rel_path, filename=original_name, mime=mime, size=size, width=width, height=height, folder_id=folder_id)
    db.session.add(mf)
    db.session.commit()
    flash("Uploaded.", "success")
    return redirect(url_for("media.media_list", folder_id=folder_id))


@media_bp.post("/media/<int:file_id>/delete")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def media_delete(file_id: int):
    mf = db.session.get(MediaFile, file_id)
    if not mf:
        abort(404)

    root = _uploads_root()
    originals_path = root / mf.path
    thumb_path = root / "thumbs" / Path(mf.path).name
    try:
        originals_path.unlink(missing_ok=True)
        thumb_path.unlink(missing_ok=True)
    except OSError:
        pass

    db.session.delete(mf)
    db.session.commit()
    flash("Deleted.", "success")
    return redirect(url_for("media.media_list"))


@media_bp.post("/media/<int:file_id>/save_edit")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def media_save_edit(file_id: int):
    data = request.get_json()
    if not data or "image" not in data:
        return {"error": "No image data"}, 400
    
    mf = db.session.get(MediaFile, file_id)
    if not mf:
        return {"error": "File not found"}, 404
        
    # Decode base64
    try:
        header, encoded = data["image"].split(",", 1)
        image_data = base64.b64decode(encoded)
    except:
        return {"error": "Invalid image data"}, 400
    
    root = _uploads_root()
    stored_path = root / mf.path
    thumb_path = root / "thumbs" / stored_path.name
    
    # Save original (overwrite as WebP)
    with open(stored_path, "wb") as f:
        f.write(image_data)
        
    # Update size and dimensions
    with Image.open(io.BytesIO(image_data)) as im:
        mf.width, mf.height = im.size
        mf.size = len(image_data)
        # Generate new thumbnail
        im.thumbnail((400, 400))
        im.save(thumb_path, "WEBP")
    
    db.session.commit()
    return {"success": True}


@media_bp.get("/uploads/<path:relpath>")
def uploads_serve(relpath: str):
    # Public serving for theme embedding. Hardening can add signed URLs later.
    relpath = relpath.replace("\\", "/")
    if ".." in relpath:
        abort(400)
    root = _uploads_root()
    directory = root
    return send_from_directory(directory, relpath, as_attachment=False)

