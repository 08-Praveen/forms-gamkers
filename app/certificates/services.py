from html import escape
from pathlib import Path

import pandas as pd
from flask import current_app

from app.certificates.generator import generate_certificate_number, generate_pdf, generate_public_token
from app.certificates.models import CertificateBatch, CertificateRecord
from app.extensions import db
from app.mail import send_email
from app.organization.models import Organization
from app.security import valid_email
from app.urls import absolute_app_url
from app.utils import utcnow

NAME_COLUMNS = {"name", "student_name", "recipient_name", "certificate_name"}
COLLEGE_COLUMNS = {
    "college_name",
    "college",
    "institution",
    "institution_name",
    "organisation",
    "organisation_name",
    "organization",
    "organization_name",
}
EMAIL_COLUMNS = {"email", "email_address", "recipient_email"}
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _normalise_column(value):
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _find_column(columns, candidates):
    normalized = {_normalise_column(column): column for column in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def read_recipients(file_or_path, filename):
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Upload a CSV, XLSX or XLS recipient list.")
    try:
        if extension == ".csv":
            dataframe = pd.read_csv(file_or_path, nrows=current_app.config["CERTIFICATE_MAX_RECORDS"] + 1)
        else:
            dataframe = pd.read_excel(
                file_or_path, nrows=current_app.config["CERTIFICATE_MAX_RECORDS"] + 1
            )
    except Exception as error:
        raise ValueError("The uploaded recipient file could not be read.") from error
    if dataframe.empty:
        raise ValueError("The uploaded file contains no recipient records.")
    if len(dataframe) > current_app.config["CERTIFICATE_MAX_RECORDS"]:
        raise ValueError(
            f"Generate at most {current_app.config['CERTIFICATE_MAX_RECORDS']} certificates per batch."
        )
    name_column = _find_column(dataframe.columns, NAME_COLUMNS)
    college_column = _find_column(dataframe.columns, COLLEGE_COLUMNS)
    email_column = _find_column(dataframe.columns, EMAIL_COLUMNS)
    if name_column is None or college_column is None:
        raise ValueError(
            "The file must include a name column and a college_name or institution column."
        )

    records = []
    for row in dataframe.to_dict(orient="records"):
        name_value = row.get(name_column)
        college_value = row.get(college_column)
        email_value = row.get(email_column) if email_column else None
        name = "" if pd.isna(name_value) else str(name_value).strip()
        college = "" if pd.isna(college_value) else str(college_value).strip()
        email = (
            "" if email_value is None or pd.isna(email_value) else str(email_value).strip()
        )
        if name and college:
            if len(name) > 180 or len(college) > 180 or len(email) > 255:
                raise ValueError("Recipient names, institutions or email addresses are too long.")
            records.append(
                {
                    "name": name,
                    "college_name": college,
                    "email": email or None,
                }
            )
    if not records:
        raise ValueError("No rows contain both a recipient name and institution.")
    return records


def create_certificate_batch(
    *,
    organization_id,
    creator_id,
    title,
    description,
    records,
    source_form_id=None,
    source_filename=None,
):
    if not records or len(records) > current_app.config["CERTIFICATE_MAX_RECORDS"]:
        raise ValueError("The certificate batch has no recipients or exceeds the batch limit.")
    batch = CertificateBatch(
        organization_id=organization_id,
        creator_id=creator_id,
        source_form_id=source_form_id,
        title=title,
        description=description,
        source_filename=source_filename,
        total_records=len(records),
        status="processing",
    )
    db.session.add(batch)
    db.session.commit()

    storage_root = Path(current_app.config["CERTIFICATE_STORAGE_PATH"]).resolve()
    generated = failed = 0
    for item in records:
        token = generate_public_token()
        certificate = CertificateRecord(
            batch_id=batch.id,
            submission_id=item.get("submission_id"),
            recipient_name=item["name"],
            college_name=item["college_name"],
            recipient_email=item.get("email"),
            certificate_number=f"PENDING-{token[:20]}",
            public_token=token,
            status="pending",
        )
        db.session.add(certificate)
        db.session.flush()
        certificate.certificate_number = generate_certificate_number(certificate.id)

        relative_path = Path(str(organization_id), str(batch.id), f"{token[:24]}.pdf")
        pdf_path = (storage_root / relative_path).resolve()
        if storage_root not in pdf_path.parents:
            raise RuntimeError("The generated certificate path escaped the private storage directory.")
        try:
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            generate_pdf(
                title=title,
                description=description,
                name=item["name"],
                college_name=item["college_name"],
                certificate_number=certificate.certificate_number,
                output_path=pdf_path,
                issue_date=certificate.created_at.strftime("%d %B %Y"),
            )
            certificate.pdf_path = relative_path.as_posix()
            certificate.status = "generated"
            generated += 1
        except Exception:
            current_app.logger.exception(
                "Certificate PDF generation failed for certificate id=%s.", certificate.id
            )
            pdf_path.unlink(missing_ok=True)
            certificate.status = "failed"
            failed += 1
        db.session.commit()
        if certificate.status == "generated":
            certificate.notification_status = _send_certificate_link(
                certificate, title, organization_id
            )
            db.session.commit()

    batch.generated_records = generated
    batch.failed_records = failed
    batch.status = "completed" if not failed else "completed_with_errors"
    batch.completed_at = utcnow()
    db.session.commit()
    return batch


def _send_certificate_link(certificate, batch_title, organization_id):
    email = certificate.recipient_email
    if not email or not valid_email(email):
        return "skipped"
    try:
        public_url = absolute_app_url(
            "certificates.public_certificate", token=certificate.public_token
        )
        body = (
            f"<p>Hello {escape(certificate.recipient_name)},</p>"
            f"<p>Your certificate for <strong>{escape(batch_title)}</strong> is ready.</p>"
            f"<p>Certificate number: <strong>{escape(certificate.certificate_number)}</strong></p>"
            f'<p><a href="{escape(public_url, quote=True)}">View and download your certificate</a></p>'
            "<p>Keep this link to access your certificate in the future.</p>"
        )
        organization = db.session.get(Organization, organization_id)
        sent = send_email(
            email,
            f"Your certificate is ready — {batch_title}",
            body,
            organization,
            "html",
        )
        return "sent" if sent else "not_configured"
    except Exception:
        current_app.logger.exception(
            "Certificate notification delivery failed for certificate id=%s.",
            certificate.id,
        )
        return "failed"
