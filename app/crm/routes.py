from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required
import requests

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


# --- FORM BUILDER ROUTES ---

@crm_bp.get("/crm/forms")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def forms_list():
    from ..models.crm import Form
    forms = db.session.execute(db.select(Form).order_by(Form.created_at.desc())).scalars().all()
    return render_template("admin/crm/forms/list.html", forms=forms)


@crm_bp.route("/crm/forms/new", methods=["GET", "POST"])
@crm_bp.route("/crm/forms/<int:form_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def forms_edit(form_id: int | None = None):
    from ..models.crm import Form
    form = db.session.get(Form, form_id) if form_id else None
    
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        fields_json = (request.form.get("fields_json") or "[]").strip()
        recipient = (request.form.get("email_recipient") or "").strip()
        webhook_url = (request.form.get("webhook_url") or "").strip()
        success_msg = (request.form.get("success_message") or "Thank you!").strip()
        
        if not name:
            flash("Form name is required.", "danger")
        else:
            if not form:
                form = Form(name=name)
                db.session.add(form)
            
            form.name = name
            form.fields_json = fields_json
            form.email_recipient = recipient
            form.webhook_url = webhook_url
            form.success_message = success_msg
            
            db.session.commit()
            flash("Form saved.", "success")
            return redirect(url_for("crm.forms_list"))
            
    return render_template("admin/crm/forms/edit.html", form=form)


@crm_bp.route("/crm/forms/<int:form_id>/delete", methods=["POST"])
@login_required
@require_roles(UserRole.ADMIN)
def forms_delete(form_id: int):
    from ..models.crm import Form
    form = db.session.get(Form, form_id)
    if form:
        db.session.delete(form)
        db.session.commit()
        flash("Form deleted.", "success")
    return redirect(url_for("crm.forms_list"))


@crm_bp.get("/crm/forms/<int:form_id>/submissions")
@login_required
@require_roles(UserRole.ADMIN, UserRole.EDITOR)
def form_submissions_list(form_id: int):
    from ..models.crm import Form, FormSubmission
    import json
    form = db.session.get(Form, form_id)
    if not form: abort(404)
    submissions = db.session.execute(db.select(FormSubmission).where(FormSubmission.form_id == form.id).order_by(FormSubmission.created_at.desc())).scalars().all()
    
    # Parse JSON for template
    parsed_submissions = []
    for s in submissions:
        try:
            parsed_submissions.append({
                "id": s.id,
                "data": json.loads(s.data_json),
                "created_at": s.created_at
            })
        except:
            continue
            
    return render_template("admin/crm/forms/submissions_list.html", form=form, submissions=parsed_submissions)


# --- PUBLIC FORM SUBMISSION ---

@crm_bp.post("/forms/submit/<int:form_id>")
def forms_submit_public(form_id: int):
    from ..models.crm import Form, FormSubmission, Contact, Lead, LeadNote
    from ..utils.email import send_email
    import json
    
    form = db.session.get(Form, form_id)
    if not form: abort(404)
    
    # Process form data
    submission_data = {}
    email_for_crm = None
    name_for_crm = "Form User"
    
    # Fields defined in form
    try:
        fields = json.loads(form.fields_json)
    except:
        fields = []
        
    for field in fields:
        val = request.form.get(field.get("name"))
        submission_data[field.get("label", field.get("name"))] = val
        
        # Heuristic for CRM
        if field.get("type") == "email" or "email" in field.get("name", "").lower():
            if not email_for_crm: email_for_crm = val
        if "name" in field.get("name", "").lower():
            name_for_crm = val

    # Save submission
    sub = FormSubmission(form_id=form.id, data_json=json.dumps(submission_data))
    db.session.add(sub)
    
    # CRM Integration
    if email_for_crm:
        contact = db.session.execute(db.select(Contact).where(Contact.email == email_for_crm)).scalar_one_or_none()
        if not contact:
            contact = Contact(name=name_for_crm, email=email_for_crm)
            db.session.add(contact)
            db.session.flush()
        
        lead = Lead(contact_id=contact.id, stage="new", source=f"Form: {form.name}")
        db.session.add(lead)
        db.session.flush()
        
        # Find an admin for note creator
        admin = db.session.execute(db.select(User).where(User.role == UserRole.ADMIN)).scalars().first()
        admin_id = admin.id if admin else 1
        
        note_body = f"Form '{form.name}' submitted.\nData:\n"
        for label, val in submission_data.items():
            note_body += f"{label}: {val}\n"
            
        note = LeadNote(lead_id=lead.id, body=note_body, created_by_id=admin_id)
        db.session.add(note)

    db.session.commit()
    
    # Send Email via Postmark
    if form.email_recipient:
        subject = f"New Submission: {form.name}"
        html_body = f"<h3>New Submission for {form.name}</h3><ul>"
        for label, val in submission_data.items():
            html_body += f"<li><strong>{label}:</strong> {val}</li>"
        html_body += "</ul>"
        
        send_email(subject, form.email_recipient, html_body)
            
    # Trigger Webhook
    if form.webhook_url:
        try:
            payload = {
                "form_id": form.id,
                "form_name": form.name,
                "submission_id": sub.id,
                "data": submission_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            requests.post(form.webhook_url, json=payload, timeout=5)
        except Exception as e:
            current_app.logger.error(f"Webhook failed for form {form.id}: {str(e)}")

    flash(form.success_message or "Thank you!", "success")
    return redirect(request.referrer or url_for("public.home"))

