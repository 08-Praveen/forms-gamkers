import json
import uuid

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db, limiter
from app.forms.csv_export import export_filename, iter_csv_rows
from app.forms.validation import QUESTION_TYPES, validate_answers, validate_questions
from app.mail import send_email
from app.models import Form, Submission


forms = Blueprint("forms", __name__)


def owned_form(form_id):
    return Form.query.filter_by(
        id=form_id, organization_id=current_user.organization_id
    ).first_or_404()


def render_editor(form, status=400):
    initial_questions = form.questions if form else []
    raw_questions = request.form.get("questions")
    if raw_questions:
        try:
            parsed = json.loads(raw_questions)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            initial_questions = []
            for item in parsed[:30]:
                if not isinstance(item, dict):
                    continue
                question_type = item.get("type")
                options = item.get("options", [])
                if not isinstance(options, list):
                    options = []
                initial_questions.append(
                    {
                        "id": item.get("id") if isinstance(item.get("id"), str) else "",
                        "title": item.get("title") if isinstance(item.get("title"), str) else "",
                        "type": (
                            question_type
                            if isinstance(question_type, str) and question_type in QUESTION_TYPES
                            else "short_text"
                        ),
                        "required": item.get("required") is True,
                        "options": [
                            value[:120] for value in options if isinstance(value, str)
                        ][:20],
                    }
                )
    return render_template(
        "forms/editor.html", form=form, initial_questions=initial_questions
    ), status


@forms.route("/forms/new", methods=["GET", "POST"])
@login_required
def create_form():
    if request.method == "POST":
        return save_form(None)
    return render_template("forms/editor.html", form=None)


@forms.route("/forms/<int:form_id>/edit", methods=["GET", "POST"])
@login_required
def edit_form(form_id):
    form = owned_form(form_id)
    if request.method == "POST":
        return save_form(form)
    return render_template("forms/editor.html", form=form)


def save_form(form):
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    subject = request.form.get("confirmation_subject", "").strip()
    body = request.form.get("confirmation_body", "").strip()
    if not title or len(title) > 180 or len(description) > 5000:
        flash("Enter a title and a description under 5,000 characters.", "error")
        return render_editor(form)
    if not subject or len(subject) > 200 or "\r" in subject or "\n" in subject:
        flash("Enter an email subject of up to 200 characters on one line.", "error")
        return render_editor(form)
    if not body or len(body) > 5000:
        flash("Enter a confirmation email message under 5,000 characters.", "error")
        return render_editor(form)
    try:
        questions = validate_questions(request.form.get("questions", ""))
    except ValueError as error:
        flash(str(error), "error")
        return render_editor(form)
    should_publish = request.form.get("publish") == "yes"
    if should_publish and not any(
        question["type"] == "email" and question["required"] for question in questions
    ):
        flash("Add a required email question before publishing so respondents can receive confirmations.", "error")
        return render_editor(form)
    if form is None:
        form = Form(
            organization_id=current_user.organization_id,
            creator_id=current_user.id,
            public_id=uuid.uuid4().hex,
        )
    form.title = title
    form.description = description
    form.questions = questions
    form.confirmation_subject = subject
    form.confirmation_body = body
    form.is_published = should_publish
    db.session.add(form)
    db.session.commit()
    flash("Form published." if form.is_published else "Draft saved.", "success")
    return redirect(url_for("forms.edit_form", form_id=form.id))


@forms.post("/forms/<int:form_id>/delete")
@login_required
def delete_form(form_id):
    form = owned_form(form_id)
    db.session.delete(form)
    db.session.commit()
    flash("Form and its responses deleted.", "success")
    return redirect(url_for("main.dashboard"))


@forms.get("/forms/<int:form_id>/responses")
@login_required
def responses(form_id):
    form = owned_form(form_id)
    submissions = Submission.query.filter_by(form_id=form.id).order_by(Submission.submitted_at.desc()).all()
    return render_template("forms/responses.html", form=form, submissions=submissions)


@forms.get("/forms/<int:form_id>/export.csv")
@forms.get("/forms/<int:form_id>/export-csv")
@login_required
def export_csv(form_id):
    form = owned_form(form_id)
    questions = form.questions or []
    question_ids = [question["id"] for question in questions]
    header = ["Submission ID", "Submitted At (UTC)", "Respondent Email"] + [
        question.get("title", question["id"]) for question in questions
    ]
    target_form_id = form.id

    def rows():
        yield header
        submissions = db.session.scalars(
            db.select(Submission)
            .where(Submission.form_id == target_form_id)
            .order_by(Submission.submitted_at.desc(), Submission.id.desc())
            .execution_options(yield_per=500)
        )
        for submission in submissions:
            answers = submission.answers or {}
            yield [
                submission.id,
                submission.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
                submission.respondent_email,
                *(answers.get(question_id) for question_id in question_ids),
            ]

    response = Response(
        stream_with_context(iter_csv_rows(rows())),
        content_type="text/csv; charset=utf-8",
    )
    filename = export_filename(form.id, form.title)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@forms.get("/forms/<int:form_id>/responses/<int:submission_id>")
@login_required
def response_detail(form_id, submission_id):
    form = owned_form(form_id)
    submission = Submission.query.filter_by(id=submission_id, form_id=form.id).first_or_404()
    questions = {question["id"]: question["title"] for question in form.questions}
    return render_template(
        "forms/response_detail.html", form=form, submission=submission, questions=questions
    )


@forms.route("/f/<public_id>", methods=["GET", "POST"])
@limiter.limit("20 per minute", methods=["POST"])
def public_form(public_id):
    form = db.session.scalar(
        db.select(Form).where(Form.public_id == public_id, Form.is_published.is_(True))
    )
    if not form:
        return render_template("errors/404.html"), 404
    if request.method == "GET":
        return render_template("forms/public_form.html", form=form)
    try:
        answers, recipient = validate_answers(form.questions, request.form)
    except ValueError as error:
        flash(str(error), "error")
        return render_template("forms/public_form.html", form=form), 400
    submission = Submission(form_id=form.id, answers=answers, respondent_email=recipient)
    db.session.add(submission)
    db.session.commit()

    email_status = "not_configured"
    if recipient:
        subject = form.confirmation_subject.replace("{email}", recipient)
        body = form.confirmation_body
        for question in form.questions:
            value = answers[question["id"]]
            replacement = ", ".join(value) if isinstance(value, list) else str(value)
            subject = subject.replace("{" + question["id"] + "}", replacement)
            body = body.replace("{" + question["id"] + "}", replacement)
        if "\r" in subject or "\n" in subject:
            subject = "Thanks for your response"
        body = body.replace("{email}", recipient)
        try:
            sent = send_email(recipient, subject, body, form.organization)
            email_status = "sent" if sent else "not_configured"
        except Exception:
            current_app.logger.exception("Form confirmation email delivery failed.")
            email_status = "failed"
        submission.email_status = email_status
        db.session.commit()
    return render_template("forms/submitted.html", email_status=email_status)
