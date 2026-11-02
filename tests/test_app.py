import json
import socket
from datetime import timedelta
from types import SimpleNamespace

from app.extensions import db
from app.models import Form, Organization, PasswordReset, User, utcnow
from app.security import hash_token


def register(client, email="admin@example.com"):
    return client.post(
        "/signup",
        data={
            "name": "Alex Admin",
            "organization": "Northstar Labs",
            "email": email,
            "password": "a-very-long-password",
        },
        follow_redirects=True,
    )


def login(client, email="admin@example.com"):
    return client.post(
        "/login",
        data={"email": email, "password": "a-very-long-password"},
        follow_redirects=True,
    )


def test_signup_creates_an_admin_workspace_and_dashboard(client, app):
    response = register(client)
    assert response.status_code == 200
    assert b"NORTHSTAR LABS" in response.data
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "admin@example.com"))
        assert user.role == "org_admin"
        assert user.organization.name == "Northstar Labs"


def test_form_can_be_published_and_sends_a_confirmation(app, client, monkeypatch):
    register(client)
    questions = [
        {"id": "name", "title": "Your name", "type": "short_text", "required": True, "options": []},
        {"id": "email", "title": "Your email", "type": "email", "required": True, "options": []},
    ]
    response = client.post(
        "/forms/new",
        data={
            "title": "Workshop registration",
            "description": "Reserve a place.",
            "questions": json.dumps(questions),
            "confirmation_subject": "You're on the list, {name}",
            "confirmation_body": "Thanks {name}. We will write to {email}.",
            "publish": "yes",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        form = db.session.scalar(db.select(Form).where(Form.title == "Workshop registration"))
        assert form.is_published
        public_id = form.public_id

    sent = []
    monkeypatch.setattr("app.forms.routes.send_email", lambda *args: sent.append(args) or True)
    response = client.post(
        f"/f/{public_id}",
        data={"name": "Alex", "email": "alex@example.com"},
    )
    assert response.status_code == 200
    assert b"confirmation email is on its way" in response.data
    assert sent[0][0:3] == (
        "alex@example.com",
        "You're on the list, Alex",
        "Thanks Alex. We will write to alex@example.com.",
    )


def test_published_form_requires_respondent_email(client):
    register(client)
    response = client.post(
        "/forms/new",
        data={
            "title": "No email",
            "questions": json.dumps(
                [{"id": "name", "title": "Name", "type": "short_text", "required": True}]
            ),
            "confirmation_subject": "Thanks",
            "confirmation_body": "Received",
            "publish": "yes",
        },
    )
    assert response.status_code == 400
    assert b"Add a required email question" in response.data


def test_tenant_form_access_is_scoped_to_the_current_organisation(app, client):
    register(client)
    with app.app_context():
        other_org = Organization(name="Other company")
        other_admin = User(name="Other", email="other@example.com", role="org_admin", organization=other_org)
        other_admin.set_password("another-long-password")
        other_form = Form(
            organization=other_org,
            creator=other_admin,
            title="Private form",
            public_id="private-form",
            questions=[],
        )
        db.session.add_all([other_admin, other_form])
        db.session.commit()
        form_id = other_form.id
    assert client.get(f"/forms/{form_id}/edit").status_code == 404


def test_member_cannot_change_organisation_settings(app, client):
    register(client)
    with app.app_context():
        member = User(
            organization_id=1,
            name="Sam Member",
            email="member@example.com",
            role="member",
        )
        member.set_password("a-very-long-password")
        db.session.add(member)
        db.session.commit()
    client.post("/logout")
    login(client, "member@example.com")
    response = client.post(
        "/settings/organisation",
        data={"name": "Changed", "website": "https://example.com"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Only organisation admins" in response.data
    with app.app_context():
        assert db.session.get(Organization, 1).name == "Northstar Labs"


def test_password_reset_token_is_single_use(app, client):
    with app.app_context():
        organization = Organization(name="Northstar Labs")
        user = User(name="Alex", email="alex@example.com", role="org_admin", organization=organization)
        user.set_password("old-password-that-is-long")
        db.session.add(user)
        db.session.flush()
        token = "one-time-test-token"
        reset = PasswordReset(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(minutes=30),
        )
        db.session.add(reset)
        db.session.commit()
    response = client.post(
        f"/reset-password/{token}",
        data={"password": "new-password-that-is-long"},
        follow_redirects=True,
    )
    assert b"Your password has been updated" in response.data
    response = client.get(f"/reset-password/{token}", follow_redirects=True)
    assert b"invalid or has expired" in response.data
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "alex@example.com"))
        assert user.check_password("new-password-that-is-long")


def test_password_reset_link_uses_configured_origin_not_host_header(app, client, monkeypatch):
    with app.app_context():
        organization = Organization(name="Northstar Labs")
        user = User(name="Alex", email="alex@example.com", role="org_admin", organization=organization)
        user.set_password("old-password-that-is-long")
        db.session.add(user)
        db.session.commit()

    sent = []
    monkeypatch.setattr("app.auth.routes.send_email", lambda *args: sent.append(args) or True)
    client.post(
        "/forgot-password",
        data={"email": "alex@example.com"},
        headers={"Host": "attacker.example"},
    )
    assert sent[0][2].startswith("Reset your password")
    assert "https://forms.example/reset-password/" in sent[0][2]
    assert "attacker.example" not in sent[0][2]


def test_smtp_delivery_rejects_private_network_targets(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(
            "app.mail.socket.getaddrinfo",
            lambda *args, **kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 587))
            ],
        )
        organization = SimpleNamespace(
            smtp_host="mail.example.com",
            smtp_port=587,
            smtp_username=None,
            smtp_password_encrypted=None,
            smtp_sender="noreply@example.com",
            smtp_security="starttls",
        )
        from app.mail import send_email

        try:
            send_email("user@example.com", "Subject", "Body", organization)
        except ValueError as error:
            assert "public IP addresses" in str(error)
        else:
            raise AssertionError("Private SMTP targets must be rejected.")
