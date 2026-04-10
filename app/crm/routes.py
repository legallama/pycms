from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..auth import require_roles
from ..extensions import db
from ..models.crm import Contact, Lead, LeadNote, Task, TaskStatus
from ..models.user import User, UserRole

crm_bp = Blueprint("crm", __name__, template_folder="../templates")

PIPELINE_STAGES = ["new", "contacted", "qualified", "proposal", "won", "lost"]


@crm_bp.get("/crm")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def crm_dashboard():
    leads = db.session.execute(db.select(Lead).order_by(Lead.created_at.desc())).scalars().all()
    by_stage = {s: [] for s in PIPELINE_STAGES}
    for l in leads:
        by_stage.setdefault(l.stage, []).append(l)
    contacts_count = db.session.execute(db.select(db.func.count(Contact.id))).scalar() or 0
    leads_count = db.session.execute(db.select(db.func.count(Lead.id))).scalar() or 0
    return render_template(
        "admin/crm/dashboard.html",
        by_stage=by_stage,
        stages=PIPELINE_STAGES,
        contacts_count=contacts_count,
        leads_count=leads_count,
    )


@crm_bp.get("/crm/contacts")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def contacts_list():
    qtxt = (request.args.get("q") or "").strip()
    q = db.select(Contact).order_by(Contact.created_at.desc())
    if qtxt:
        q = q.where(Contact.name.ilike(f"%{qtxt}%"))
    contacts = db.session.execute(q).scalars().all()
    return render_template("admin/crm/contacts_list.html", contacts=contacts, q=qtxt)


@crm_bp.route("/crm/contacts/new", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def contacts_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip() or None
        phone = (request.form.get("phone") or "").strip() or None
        company = (request.form.get("company") or "").strip() or None
        if not name:
            flash("Name is required.", "danger")
        else:
            c = Contact(name=name, email=email, phone=phone, company=company)
            db.session.add(c)
            db.session.commit()
            flash("Contact created.", "success")
            return redirect(url_for("crm.contacts_list"))
    return render_template("admin/crm/contacts_new.html")


@crm_bp.route("/crm/leads/new", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def leads_new():
    contacts = db.session.execute(db.select(Contact).order_by(Contact.name.asc())).scalars().all()
    users = db.session.execute(db.select(User).order_by(User.email.asc())).scalars().all()
    if request.method == "POST":
        contact_id = int(request.form.get("contact_id") or "0")
        stage = (request.form.get("stage") or "new").strip()
        source = (request.form.get("source") or "").strip() or None
        value = request.form.get("value")
        owner_id = request.form.get("owner_id")
        if stage not in PIPELINE_STAGES:
            stage = "new"

        if not contact_id:
            flash("Pick a contact.", "danger")
        else:
            lead = Lead(
                contact_id=contact_id,
                stage=stage,
                source=source,
                value=(int(value) if value else None),
                owner_id=(int(owner_id) if owner_id else None),
                created_at=datetime.utcnow(),
            )
            db.session.add(lead)
            db.session.commit()
            flash("Lead created.", "success")
            return redirect(url_for("crm.lead_detail", lead_id=lead.id))

    return render_template("admin/crm/leads_new.html", contacts=contacts, users=users, stages=PIPELINE_STAGES)


@crm_bp.get("/crm/leads/<int:lead_id>")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def lead_detail(lead_id: int):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        return ("Not Found", 404)
    contact = db.session.get(Contact, lead.contact_id)
    notes = db.session.execute(db.select(LeadNote).where(LeadNote.lead_id == lead.id).order_by(LeadNote.created_at.desc())).scalars().all()
    tasks = db.session.execute(db.select(Task).where(Task.lead_id == lead.id).order_by(Task.id.desc())).scalars().all()
    users = db.session.execute(db.select(User).order_by(User.email.asc())).scalars().all()
    return render_template(
        "admin/crm/lead_detail.html",
        lead=lead,
        contact=contact,
        notes=notes,
        tasks=tasks,
        users=users,
        stages=PIPELINE_STAGES,
        TaskStatus=TaskStatus,
    )


@crm_bp.post("/crm/leads/<int:lead_id>/stage")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def lead_set_stage(lead_id: int):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        return ("Not Found", 404)
    stage = (request.form.get("stage") or "").strip()
    if stage not in PIPELINE_STAGES:
        flash("Invalid stage.", "danger")
    else:
        lead.stage = stage
        db.session.commit()
        flash("Stage updated.", "success")
    return redirect(url_for("crm.lead_detail", lead_id=lead.id))


@crm_bp.post("/crm/leads/<int:lead_id>/notes")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def lead_add_note(lead_id: int):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        return ("Not Found", 404)
    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Note cannot be empty.", "danger")
    else:
        n = LeadNote(lead_id=lead.id, body=body, created_by_id=current_user.id)
        db.session.add(n)
        db.session.commit()
        flash("Note added.", "success")
    return redirect(url_for("crm.lead_detail", lead_id=lead.id))


@crm_bp.post("/crm/leads/<int:lead_id>/tasks")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def lead_add_task(lead_id: int):
    lead = db.session.get(Lead, lead_id)
    if not lead:
        return ("Not Found", 404)
    title = (request.form.get("title") or "").strip()
    assigned_to_id = request.form.get("assigned_to_id")
    if not title:
        flash("Task title is required.", "danger")
    else:
        t = Task(
            lead_id=lead.id,
            title=title,
            status=TaskStatus.OPEN.value,
            assigned_to_id=(int(assigned_to_id) if assigned_to_id else None),
        )
        db.session.add(t)
        db.session.commit()
        flash("Task added.", "success")
    return redirect(url_for("crm.lead_detail", lead_id=lead.id))


@crm_bp.post("/crm/tasks/<int:task_id>/toggle")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def task_toggle(task_id: int):
    t = db.session.get(Task, task_id)
    if not t:
        return ("Not Found", 404)
    t.status = TaskStatus.DONE.value if t.status != TaskStatus.DONE.value else TaskStatus.OPEN.value
    db.session.commit()
    return redirect(url_for("crm.lead_detail", lead_id=t.lead_id))

