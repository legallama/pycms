from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import login_required
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..auth import require_roles
from ..extensions import db
from ..models.media import MediaFile
from ..models.user import UserRole

media_bp = Blueprint("media", __name__, template_folder="../templates")

ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ALLOWED_OTHER_EXTS = {".pdf"}
ALLOWED_EXTS = ALLOWED_IMAGE_EXTS | ALLOWED_OTHER_EXTS
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


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


def _save_upload(fs: FileStorage) -> tuple[str, str, int, int | None, int | None]:
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
    stored_name = f"{token}{ext}"
    stored_rel = f"originals/{stored_name}"
    stored_path = originals / stored_name
    fs.save(stored_path)

    mime = fs.mimetype or "application/octet-stream"
    width = height = None
    if ext in ALLOWED_IMAGE_EXTS:
        with Image.open(stored_path) as im:
            width, height = im.size
            im.thumbnail((400, 400))
            thumb_path = thumbs / stored_name
            im.save(thumb_path)

    return stored_rel, filename, size, width, height


@media_bp.get("/media")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def media_list():
    files = db.session.execute(db.select(MediaFile).order_by(MediaFile.created_at.desc())).scalars().all()
    mode = request.args.get("mode")
    return render_template("admin/media/list.html", files=files, mode=mode)


@media_bp.post("/media/upload")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR, UserRole.AUTHOR)
def media_upload():
    fs = request.files.get("file")
    try:
        rel_path, original_name, size, width, height = _save_upload(fs)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("media.media_list"))

    mf = MediaFile(path=rel_path, filename=original_name, mime=fs.mimetype or "application/octet-stream", size=size, width=width, height=height)
    db.session.add(mf)
    db.session.commit()
    flash("Uploaded.", "success")
    return redirect(url_for("media.media_list"))


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


@media_bp.get("/uploads/<path:relpath>")
def uploads_serve(relpath: str):
    # Public serving for theme embedding. Hardening can add signed URLs later.
    relpath = relpath.replace("\\", "/")
    if ".." in relpath:
        abort(400)
    root = _uploads_root()
    directory = root
    return send_from_directory(directory, relpath, as_attachment=False)

