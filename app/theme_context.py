from __future__ import annotations

import json
from types import SimpleNamespace

from .extensions import db
from .models.navigation import Menu, MenuItem, Module


def get_main_menu_items() -> list[dict]:
    menu = db.session.execute(db.select(Menu).where(Menu.name == "main")).scalar_one_or_none()
    if not menu:
        return [{"label": "Home", "href": "/"}, {"label": "Blog", "href": "/blog"}]

    items = (
        db.session.execute(
            db.select(MenuItem)
            .where(MenuItem.menu_id == menu.id, MenuItem.parent_id.is_(None))
            .order_by(MenuItem.order.asc())
        )
        .scalars()
        .all()
    )

    out = []
    for it in items:
        href = it.url or "/"
        out.append({"label": it.label, "href": href})
    return out


def get_modules_by_position() -> SimpleNamespace:
    mods = (
        db.session.execute(db.select(Module).where(Module.enabled.is_(True)).order_by(Module.position.asc(), Module.order.asc()))
        .scalars()
        .all()
    )
    buckets: dict[str, list[dict]] = {}
    for m in mods:
        cfg = {}
        try:
            cfg = json.loads(m.config_json or "{}")
        except json.JSONDecodeError:
            cfg = {}

        if m.type == "html":
            payload = {"title": m.title, "html": cfg.get("html", "")}
        else:
            payload = {"title": m.title, "html": ""}

        buckets.setdefault(m.position, []).append(payload)

    return SimpleNamespace(**{k: v for k, v in buckets.items()})

