# Forms Gamkers

A multi-tenant form and response platform built with Flask, SQLAlchemy, MySQL and
server-rendered templates. The interface uses Gamkers' dark, green-accented
cybersecurity brand direction.

## What is included

- Organisation signup, login, logout, single-use password reset links and team invitations.
- Organisation-scoped workspaces with `org_admin` and `member` roles.
- Form builder for short/long text, email, number, date, multiple-choice and checkbox questions.
- Draft/publish controls, public response links and organisation-only response details.
- CSV export of responses, hardened against spreadsheet formula injection: cells
  starting with `=`, `+`, `-`, `@`, tab or carriage return are prefixed with `'`
  (plain numbers are safely preserved without quotes).
- Custom confirmation email subject/body with `{email}` and question-ID placeholders.
- Confirmation messages can be plain text, sanitised HTML or Markdown. Every email
  receives the built-in responsive style, rendered with Tailwind CSS and inlined
  for email clients.
- Event forms can store local date/time, an IANA timezone and venue/meeting link.
  Confirmation emails show those details, link to Google Calendar, and attach a
  calendar invitation for compatible calendar apps.
- Closing a published event form displays the creator's message and creates a
  separate, published feedback form for attendees.
- Certificate generation from feedback responses or CSV/XLS/XLSX recipient lists,
  previewed batch imports, CSV/XLSX exports, and permanent public verification
  links for generated PDFs. Generated certificates are emailed to valid recipient
  email addresses when organisation or platform SMTP is configured.
- Single-source Tailwind CSS v4 build pipeline for the application and confirmation emails.
- Organisation SMTP settings, encrypted SMTP passwords and platform SMTP fallback.
- CSRF protection, secure password hashing, request-size limits, login/form rate limits,
  scoped data queries and browser security headers.
- Flask-SQLAlchemy models and Flask-Migrate/Alembic database migrations.

An organisation admin can edit organisation details, SMTP settings, team roles, all
forms in their organisation and its responses. Members can create and edit forms
in their organisation and view its responses. An organisation must retain at
least one admin.

## Application structure

The application uses a Flask application factory and feature blueprints. Each
feature owns its routes and data models; shared infrastructure such as database
extensions, security helpers, and email delivery stays in focused modules.

```text
app/
  auth/          authentication routes and identity models
  certificates/  certificate routes, models, generation, and batch services
  forms/         form routes, models, validation, and exports
  main/          landing page and workspace routes
  organization/  organisation routes and models
  templates/     server-rendered pages, grouped by feature
  static/        compiled Tailwind CSS and browser JavaScript
  extensions.py  shared Flask extensions
  models.py      model registry used by migrations and compatibility imports
  mail.py        confirmation and account email delivery
```

Keep new feature logic in its owning package. Register new models in the model
registry so Alembic can discover them, then add a reviewed migration for schema
changes.

## Local development

Use Python 3.11 or newer.

```text
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm ci
npm run build:css
copy .env.example .env
```

Copy `.env.example` to `.env`. Replace the `SECRET_KEY` and
`SMTP_ENCRYPTION_KEY` placeholders with generated values:

```text
python -c "import secrets; print(secrets.token_hex(32))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use the first command's output for `SECRET_KEY` and the second for
`SMTP_ENCRYPTION_KEY`. Replace the example DB name, DB user and DB password with
your local MySQL credentials. The example SMTP values are placeholders; configure
them only if you need the platform SMTP fallback. Never commit `.env`.
The application requires MySQL; the test suite uses SQLite by default.
Initialise the schema and run the test suite:

```text
flask --app wsgi db upgrade
pytest
flask --app wsgi run
```

The migrations are included in `migrations/`; apply them with `db upgrade`.
For later model changes, create a revision with `db migrate`, review and commit
the generated operations, then apply them with `db upgrade`. Never use
`db.create_all()` as a production schema migration.

## MySQL and phpMyAdmin

phpMyAdmin is the web interface for creating and managing the database and
importing SQL; it does not connect the Flask application to MySQL. Flask reads
the connection directly from `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and
`DB_PASSWORD` in `.env`. No database URL needs to be constructed or encoded.

Create a MySQL database and user in cPanel, grant that user access to the
database, and enter the five settings in your private `.env`. Use the exact
database/user names shown in cPanel; they commonly include the cPanel account
prefix. The host is often `localhost`, but use the hostname provided by your
hosting provider. SQLAlchemy safely handles special characters in
`DB_PASSWORD`. Also set production `SECRET_KEY`, `SMTP_ENCRYPTION_KEY`,
`APPLICATION_BASE_URL=https://your-domain`, and `SECURE_COOKIES=1`. Keep secrets
in the private `.env` or cPanel environment settings, never in source control.
Back up the MySQL database and test restoration before accepting real responses.

Use MySQL 5.7.8+ or MariaDB 10.2.7+ with InnoDB. Older servers lack the `JSON`
column type and reject the utf8mb4 unique index on `user.email`. Set the
database default to `utf8mb4` / `utf8mb4_unicode_ci` **before** creating tables
in cPanel/phpMyAdmin. The import script does not change database-level settings,
so it does not require `ALTER DATABASE` privileges. A `latin1` database can
corrupt non-ASCII answers.

The app pings pooled connections before use and recycles them after 280 seconds,
so shared-host idle timeouts do not surface as `MySQL server has gone away
(2006)`. On MySQL each process opens at most 10 connections (`pool_size=5`,
`max_overflow=5`). Keep the number of application processes multiplied by 10
below the host's `max_user_connections`.

## cPanel / Passenger WSGI deployment

1. In **Setup Python App**, create a Python 3.11+ application. Keep the project
   outside `public_html` where possible, and use the domain/subdomain and HTTPS
   certificate assigned to the app.
2. Upload the repository including `passenger_wsgi.py`, `wsgi.py`, `app/`,
   `migrations/`, and `requirements.txt`. Set the application startup file to
   `passenger_wsgi.py` and the entry point to `application`.
3. Use the virtual environment path shown by cPanel to install
   `requirements.txt`. If the host does not offer a compatible Python/MySQL
   driver, ask the provider to enable PyMySQL outbound database connectivity.
4. Create a MySQL database/user in cPanel and grant that user access to the
   application database. Copy `.env.example` to `.env` in the project directory
   (never inside `public_html`) and set `DB_HOST`, `DB_PORT`, `DB_NAME`,
   `DB_USER`, and `DB_PASSWORD` from cPanel. Also set the canonical HTTPS
   `APPLICATION_BASE_URL`, `SECRET_KEY`, `SMTP_ENCRYPTION_KEY`, and
   `SECURE_COOKIES=1`. Alternatively, enter these same variables in cPanel's
   Python App configuration. The app loads `.env` at startup. The `memory://`
   rate limiter is process-local; use shared Redis storage if the host offers
   Redis and install its Python client.
5. Create the schema once, using one of these options:
   - **SSH available:** from the cPanel application virtual environment, run
     `flask --app wsgi db upgrade`. Run it again whenever a reviewed database
     migration is deployed.
   - **No SSH (phpMyAdmin only):** select the empty application database, open
     **Import** and import `deploy/schema_mysql.sql`. The selected database must
     already use the `utf8mb4_unicode_ci` collation; the script creates every table
     and records the current Alembic revision.
     For later migrations, generate incremental SQL on a development machine
     with `flask --app wsgi db upgrade <current_revision>:head --sql` using the
     cPanel MySQL settings, then import that file the same way.

   Do not expose `.env`, virtualenvs, logs or database backups through the
   document root.
6. Restart the Passenger application and check its error log. Configure your
   organisation's SMTP account under **Settings → Email delivery** before
   inviting teammates or publishing forms that send confirmations.
7. Verify HTTPS, signup, a team invitation, form submission, response visibility,
   confirmation delivery, password recovery, certificate upload and public
   download, backup and restore on the deployed domain before opening the service.

The compiled Tailwind stylesheet is included in the repository; Node.js is
only needed to rebuild it when changing CSS or templates (`npm ci`, then
`npm run build:css`). Keep certificate storage on persistent disk outside the
web document root. By default, uploaded recipient lists and generated PDF
certificates are stored under the Flask `instance/certificates` directory.
Staged uploads expire after two hours and are deleted after processing.
Generated PDFs and their random public URLs are retained indefinitely. This
cPanel deployment generates up to 500 PDFs synchronously per batch; increase
that limit only after confirming the host's request timeouts and available memory.

Some cPanel plans restrict outbound SMTP. Confirm outbound SMTP/TLS and MySQL
connections with the provider. Use the organisation's authorised SMTP provider,
STARTTLS or SSL/TLS, and a sender address/domain approved by that provider.

## Email behaviour

Published forms require a required email question. The first email question is
the confirmation recipient. The subject and message support `{email}`,
`{form_title}`, `{event_date}`, `{event_time}`, `{event_location}`, and
`{question_id}` placeholders; question IDs are visible in the form builder. For
example, `{name}` resolves to the answer for question ID `name`.
Confirmation content can be plain text, HTML or Markdown. HTML is sanitised;
Tailwind's prebuilt email styles are inlined so email clients don't need an
external stylesheet. Plain text, Markdown and HTML all include a plain-text
alternative. Event forms can store an event start/end, IANA timezone and
location/meeting link. Registration email automatically includes these details,
a Google Calendar action link and a `text/calendar` invitation attachment.
Details are entered by the form creator; the application does not read Gmail.
SMTP delivery happens synchronously immediately after the response is committed.
If mail delivery fails, the response is retained, the delivery status is saved,
and the respondent sees that the confirmation could not be sent. A later
background mail queue can be introduced if the deployment outgrows cPanel's
request/worker constraints.

Organisation SMTP passwords are encrypted at rest using Fernet and
`SMTP_ENCRYPTION_KEY`. Back up this key securely: encrypted SMTP passwords
cannot be recovered without it. Rotating the key requires re-encrypting existing
credentials before removing the old key. The optional platform SMTP settings
are environment secrets and are used for password-reset email or when an
organisation has not configured its own mail account.
SMTP hostnames are resolved at send time and connections to non-public IP
addresses are rejected to prevent tenant SMTP settings from reaching internal
services.

## Event feedback and certificates

Closing a published event form requires a custom public closure message. The
registration link then stops accepting submissions and shows that message plus
a link to a newly published feedback form. That form asks for the recipient's
certificate name, institution, email, event rating and optional feedback.
Its CSV export uses the certificate-import headers `name`, `college_name`,
`email`, `rating`, and `feedback`, and can be uploaded directly to the
certificate generator.

Organisation members and admins can issue one certificate per eligible feedback
response from the closed event. They can also upload a CSV/XLS/XLSX file with
`name` and `college_name` or institution columns, review a preview and generate
a batch. Certificates use a modern, vector-drawn PDF layout without embedded
base64 images. When SMTP is configured, each generated certificate with a valid
recipient email gets an email containing its permanent public link. Each batch
records email delivery status; missing addresses are marked skipped and
delivery failures remain visible without discarding generated certificates.
Batch results include individual, random-token public verification/download
URLs and CSV/XLSX exports. Generated PDFs are never stored in the web-accessible
static directory.

Certificate description placeholders are `{name}`, `{college_name}`,
`{certificate_number}` and `{date}`. Each form submission can receive a
certificate only once. Certificate generation and email delivery are synchronous;
large batches may exceed shared-host request timeouts. Public links do not expire;
retain the database and private certificate storage together when making backups
or moving hosts.

## Tests

```text
pytest
```

Tests use an isolated in-memory SQLite database by default and do not send real
email. To run the suite against MySQL or MariaDB, set `TEST_DB_HOST`,
`TEST_DB_PORT`, `TEST_DB_NAME`, `TEST_DB_USER`, and `TEST_DB_PASSWORD` to an
empty, disposable database (tables are created and dropped for every test):

```text
TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=3306 TEST_DB_NAME=forms_test TEST_DB_USER=forms_test TEST_DB_PASSWORD='replace-me' pytest
```
