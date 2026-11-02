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
- Organisation SMTP settings, encrypted SMTP passwords and platform SMTP fallback.
- CSRF protection, secure password hashing, request-size limits, login/form rate limits,
  scoped data queries and browser security headers.
- Flask-SQLAlchemy models and Flask-Migrate/Alembic database migrations.

An organisation admin can edit organisation details, SMTP settings, team roles, all
forms in their organisation and its responses. Members can create and edit forms
in their organisation and view its responses. An organisation must retain at
least one admin.

## Local development

Use Python 3.11 or newer.

```text
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env
```

Set a private `SECRET_KEY`, the canonical `APPLICATION_BASE_URL`, and generate
a Fernet key for `SMTP_ENCRYPTION_KEY`:

```text
python -c "import secrets; print(secrets.token_hex(32))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put each generated value in `.env`. The default SQLite URL is only for local
development. Initialise the schema and run the test suite:

```text
flask --app wsgi db upgrade
pytest
flask --app wsgi run
```

The initial migration is included in `migrations/`; apply it with `db upgrade`.
For later model changes, create a revision with `db migrate`, review and commit
the generated operations, then apply them with `db upgrade`. Never use
`db.create_all()` as a production schema migration.

## MySQL configuration

Create a dedicated database and least-privilege database user. Set `DATABASE_URL`
to a SQLAlchemy URL such as:

```text
mysql+pymysql://forms_user:URL_ENCODED_PASSWORD@localhost/forms_gamkers?charset=utf8mb4
```

URL-encode special characters in the database username/password. Configure a
production `SECRET_KEY`, `SMTP_ENCRYPTION_KEY`, and `SECURE_COOKIES=1`. Keep all
secrets in the hosting provider's environment settings, not in source control.
Back up the MySQL database and test restoration before accepting real responses.

Use MySQL 5.7.8+ or MariaDB 10.2.7+ with InnoDB. Older servers lack the `JSON`
column type and reject the utf8mb4 unique index on `user.email`. Set the
database default to `utf8mb4` / `utf8mb4_unicode_ci` **before** creating tables
(phpMyAdmin → database → **Operations** → **Collation**, or run
`ALTER DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`). Tables
inherit this default, and a `latin1` database corrupts non-ASCII answers.

The app pings pooled connections before use and recycles them after 280 seconds,
so shared-host idle timeouts do not surface as `MySQL server has gone away
(2006)`. On MySQL each process opens at most 10 connections (`pool_size=5`,
`max_overflow=5`). Keep processes × 10 below the host's `max_user_connections`.

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
   application database. Add these environment variables in the Python App
   configuration:
   - `SECRET_KEY`: output of `python -c "import secrets; print(secrets.token_hex(32))"`.
   - `SMTP_ENCRYPTION_KEY`: output of the Fernet key-generation command above.
   - `APPLICATION_BASE_URL`: the canonical HTTPS origin of the application (used
     for password-reset and invitation links; do not derive these links from the
     incoming Host header).
   - `DATABASE_URL`: the encoded `mysql+pymysql://...` URL.
   - `SECURE_COOKIES=1`.
   - `RATELIMIT_STORAGE_URI`: a shared Redis URL if Redis is available. The
     built-in `memory://` limiter is suitable for local development, not
     multi-process production deployments.
   Alternatively, copy `.env.cpanel.example` to `.env` in the project directory
   (never inside `public_html`) and fill in the same values. The app loads it at startup.
5. Create the schema once, using one of these options:
   - **SSH available:** from the cPanel application virtual environment, run
     `flask --app wsgi db upgrade`. Run it again whenever a reviewed database
     migration is deployed.
   - **No SSH (phpMyAdmin only):** select the empty application database, open
     **Import** and import `deploy/schema_mysql.sql`. It switches the database to
     utf8mb4, creates every table and records Alembic revision `d6fd79910711`.
     For later migrations, generate incremental SQL on a development machine with
     `flask --app wsgi db upgrade <current_revision>:head --sql` (using a
     `mysql+pymysql://` `DATABASE_URL`) and import that file the same way.

   Do not expose `.env`, virtualenvs, logs or database backups through the
   document root.
6. Restart the Passenger application and check its error log. Configure your
   organisation's SMTP account under **Settings → Email delivery** before
   inviting teammates or publishing forms that send confirmations.
7. Verify HTTPS, signup, a team invitation, form submission, response visibility,
   confirmation delivery, password recovery, backup and restore on the deployed
   domain before opening the service to users.

Some cPanel plans restrict outbound SMTP. Confirm outbound SMTP/TLS and MySQL
connections with the provider. Use the organisation's authorised SMTP provider,
STARTTLS or SSL/TLS, and a sender address/domain approved by that provider.

## Email behaviour

Published forms require a required email question. The first email question is
the confirmation recipient. The subject and message support `{email}` and
`{question_id}` placeholders; question IDs are visible in the form builder.
For example, `{name}` resolves to the answer for question ID `name`. SMTP
delivery happens synchronously immediately after the response is committed.
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

## Tests

```text
pytest
```

Tests use an isolated in-memory SQLite database by default and do not send real
email. To run the same suite against MySQL or MariaDB, point `TEST_DATABASE_URL`
at an empty, disposable database (tables are created and dropped for every test):

```text
TEST_DATABASE_URL='mysql+pymysql://user:pass@127.0.0.1:3306/forms_test?charset=utf8mb4' pytest
```
