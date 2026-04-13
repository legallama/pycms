import enum
from datetime import datetime, timezone

from ..extensions import db


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    DONE = "done"


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True, index=True)
    phone = db.Column(db.String(50), nullable=True)
    company = db.Column(db.String(255), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False, index=True)
    stage = db.Column(db.String(50), nullable=False, default="new", index=True)
    source = db.Column(db.String(100), nullable=True)
    value = db.Column(db.Integer, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class LeadNote(db.Model):
    __tablename__ = "lead_notes"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    due_at = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=TaskStatus.OPEN.value)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)


class Form(db.Model):
    __tablename__ = "forms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    # List of {label, type, name, required}
    fields_json = db.Column(db.Text, nullable=False, default="[]") 
    email_recipient = db.Column(db.String(255), nullable=True) # Send notification to
    success_message = db.Column(db.String(255), nullable=True, default="Thank you! Your message has been sent.")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    submissions = db.relationship("FormSubmission", back_populates="form", cascade="all, delete-orphan")


class FormSubmission(db.Model):
    __tablename__ = "form_submissions"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("forms.id"), nullable=False, index=True)
    # JSON of submitted data
    data_json = db.Column(db.Text, nullable=False) 
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    form = db.relationship("Form", back_populates="submissions")

