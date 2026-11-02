from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    website = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    smtp_host = db.Column(db.String(255))
    smtp_port = db.Column(db.Integer)
    smtp_username = db.Column(db.String(255))
    smtp_password_encrypted = db.Column(db.Text)
    smtp_sender = db.Column(db.String(255))
    smtp_security = db.Column(db.String(12), nullable=False, default="starttls")
    users = db.relationship("User", back_populates="organization", cascade="all, delete-orphan")
    forms = db.relationship("Form", back_populates="organization", cascade="all, delete-orphan")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(24), nullable=False, default="member")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    organization = db.relationship("Organization", back_populates="users")
    forms = db.relationship("Form", back_populates="creator")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_org_admin(self):
        return self.role == "org_admin"


class Form(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    public_id = db.Column(db.String(32), nullable=False, unique=True, index=True)
    questions = db.Column(db.JSON, nullable=False, default=list)
    confirmation_subject = db.Column(db.String(200), nullable=False, default="Thanks for your response")
    confirmation_body = db.Column(db.Text, nullable=False, default="Thanks for submitting this form.")
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    organization = db.relationship("Organization", back_populates="forms")
    creator = db.relationship("User", back_populates="forms")
    submissions = db.relationship("Submission", back_populates="form", cascade="all, delete-orphan")


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("form.id", ondelete="CASCADE"), nullable=False, index=True)
    answers = db.Column(db.JSON, nullable=False)
    respondent_email = db.Column(db.String(255))
    email_status = db.Column(db.String(16), nullable=False, default="not_configured")
    submitted_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    form = db.relationship("Form", back_populates="submissions")


class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)


class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email = db.Column(db.String(255), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    organization = db.relationship("Organization")


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
