import ipaddress
import socket
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

from app.security import decrypt_smtp_password


def smtp_settings(organization=None):
    if organization and organization.smtp_host and organization.smtp_sender:
        return {
            "host": organization.smtp_host,
            "port": organization.smtp_port or 587,
            "username": organization.smtp_username,
            "password": (
                decrypt_smtp_password(organization.smtp_password_encrypted)
                if organization.smtp_password_encrypted
                else None
            ),
            "sender": organization.smtp_sender,
            "security": organization.smtp_security,
        }
    config = current_app.config
    if config.get("DEFAULT_SMTP_HOST") and config.get("DEFAULT_SMTP_SENDER"):
        return {
            "host": config["DEFAULT_SMTP_HOST"],
            "port": config["DEFAULT_SMTP_PORT"],
            "username": config.get("DEFAULT_SMTP_USERNAME"),
            "password": config.get("DEFAULT_SMTP_PASSWORD"),
            "sender": config["DEFAULT_SMTP_SENDER"],
            "security": config.get("DEFAULT_SMTP_SECURITY", "starttls"),
        }
    return None


def send_email(recipient, subject, body, organization=None):
    settings = smtp_settings(organization)
    if not settings:
        return False
    if settings["security"] not in {"starttls", "ssl"}:
        raise ValueError("SMTP must use STARTTLS or SSL/TLS.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings["sender"]
    message["To"] = recipient
    message.set_content(body)
    context = ssl.create_default_context()
    addresses = socket.getaddrinfo(
        settings["host"], settings["port"], type=socket.SOCK_STREAM
    )
    public_addresses = []
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("SMTP host must resolve only to public IP addresses.")
        if ip not in public_addresses:
            public_addresses.append(ip)
    if not public_addresses:
        raise OSError("SMTP host did not resolve to an address.")
    server_host = str(public_addresses[0])
    if settings["security"] == "ssl":
        server = smtplib.SMTP_SSL(timeout=15, context=context)
    else:
        server = smtplib.SMTP(timeout=15)
    # Connect to the checked IP while retaining the configured host for TLS verification.
    server._host = settings["host"]
    server.connect(server_host, settings["port"])
    with server:
        server.ehlo()
        if settings["security"] == "starttls":
            server.starttls(context=context)
            server.ehlo()
        if settings["username"]:
            server.login(settings["username"], settings["password"] or "")
        server.send_message(message)
    return True
