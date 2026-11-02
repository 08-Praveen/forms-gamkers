-- Forms Gamkers MySQL schema for phpMyAdmin import.
-- Import once into an empty MySQL 5.7.8+ or MariaDB 10.2.7+ InnoDB database.
-- Generated from the complete Alembic migration history.
-- Regenerate with `flask --app wsgi db upgrade --sql` when migrations change.
-- Set the database collation to utf8mb4_unicode_ci in cPanel before importing.

SET NAMES utf8mb4;
SET default_storage_engine = InnoDB;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> d6fd79910711

CREATE TABLE organization (
    id INTEGER NOT NULL AUTO_INCREMENT,
    name VARCHAR(160) NOT NULL,
    website VARCHAR(255),
    created_at DATETIME NOT NULL,
    smtp_host VARCHAR(255),
    smtp_port INTEGER,
    smtp_username VARCHAR(255),
    smtp_password_encrypted TEXT,
    smtp_sender VARCHAR(255),
    smtp_security VARCHAR(12) NOT NULL,
    CONSTRAINT pk_organization PRIMARY KEY (id)
);

CREATE TABLE invitation (
    id INTEGER NOT NULL AUTO_INCREMENT,
    organization_id INTEGER NOT NULL,
    email VARCHAR(255) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    accepted_at DATETIME,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_invitation PRIMARY KEY (id),
    CONSTRAINT fk_invitation_organization_id_organization FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    CONSTRAINT uq_invitation_token_hash UNIQUE (token_hash)
);

CREATE INDEX ix_invitation_organization_id ON invitation (organization_id);

CREATE TABLE user (
    id INTEGER NOT NULL AUTO_INCREMENT,
    organization_id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    `role` VARCHAR(24) NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_user PRIMARY KEY (id),
    CONSTRAINT fk_user_organization_id_organization FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_user_email ON user (email);

CREATE TABLE form (
    id INTEGER NOT NULL AUTO_INCREMENT,
    organization_id INTEGER NOT NULL,
    creator_id INTEGER NOT NULL,
    title VARCHAR(180) NOT NULL,
    description TEXT NOT NULL,
    public_id VARCHAR(32) NOT NULL,
    questions JSON NOT NULL,
    confirmation_subject VARCHAR(200) NOT NULL,
    confirmation_body TEXT NOT NULL,
    is_published BOOL NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_form PRIMARY KEY (id),
    CONSTRAINT fk_form_creator_id_user FOREIGN KEY(creator_id) REFERENCES user (id),
    CONSTRAINT fk_form_organization_id_organization FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE
);

CREATE INDEX ix_form_organization_id ON form (organization_id);

CREATE UNIQUE INDEX ix_form_public_id ON form (public_id);

CREATE TABLE password_reset (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME,
    CONSTRAINT pk_password_reset PRIMARY KEY (id),
    CONSTRAINT fk_password_reset_user_id_user FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE,
    CONSTRAINT uq_password_reset_token_hash UNIQUE (token_hash)
);

CREATE INDEX ix_password_reset_user_id ON password_reset (user_id);

CREATE TABLE submission (
    id INTEGER NOT NULL AUTO_INCREMENT,
    form_id INTEGER NOT NULL,
    answers JSON NOT NULL,
    respondent_email VARCHAR(255),
    email_status VARCHAR(16) NOT NULL,
    submitted_at DATETIME NOT NULL,
    CONSTRAINT pk_submission PRIMARY KEY (id),
    CONSTRAINT fk_submission_form_id_form FOREIGN KEY(form_id) REFERENCES form (id) ON DELETE CASCADE
);

CREATE INDEX ix_submission_form_id ON submission (form_id);

INSERT INTO alembic_version (version_num) VALUES ('d6fd79910711');

-- Running upgrade d6fd79910711 -> f45559f86783

CREATE TABLE certificate_upload (
    id INTEGER NOT NULL AUTO_INCREMENT,
    organization_id INTEGER NOT NULL,
    creator_id INTEGER NOT NULL,
    stored_filename VARCHAR(80) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    total_records INTEGER NOT NULL,
    preview_records JSON NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_certificate_upload PRIMARY KEY (id),
    CONSTRAINT fk_certificate_upload_creator_id_user FOREIGN KEY(creator_id) REFERENCES user (id),
    CONSTRAINT fk_certificate_upload_organization_id_organization FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    CONSTRAINT uq_certificate_upload_stored_filename UNIQUE (stored_filename)
);

CREATE INDEX ix_certificate_upload_expires_at ON certificate_upload (expires_at);

CREATE INDEX ix_certificate_upload_organization_id ON certificate_upload (organization_id);

CREATE TABLE certificate_batch (
    id INTEGER NOT NULL AUTO_INCREMENT,
    organization_id INTEGER NOT NULL,
    creator_id INTEGER NOT NULL,
    source_form_id INTEGER,
    title VARCHAR(180) NOT NULL,
    description TEXT NOT NULL,
    source_filename VARCHAR(255),
    total_records INTEGER NOT NULL,
    generated_records INTEGER NOT NULL,
    failed_records INTEGER NOT NULL,
    status VARCHAR(24) NOT NULL,
    created_at DATETIME NOT NULL,
    completed_at DATETIME,
    CONSTRAINT pk_certificate_batch PRIMARY KEY (id),
    CONSTRAINT fk_certificate_batch_creator_id_user FOREIGN KEY(creator_id) REFERENCES user (id),
    CONSTRAINT fk_certificate_batch_organization_id_organization FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    CONSTRAINT fk_certificate_batch_source_form_id_form FOREIGN KEY(source_form_id) REFERENCES form (id) ON DELETE SET NULL
);

CREATE INDEX ix_certificate_batch_organization_id ON certificate_batch (organization_id);

CREATE INDEX ix_certificate_batch_source_form_id ON certificate_batch (source_form_id);

CREATE TABLE certificate_record (
    id INTEGER NOT NULL AUTO_INCREMENT,
    batch_id INTEGER NOT NULL,
    submission_id INTEGER,
    recipient_name VARCHAR(180) NOT NULL,
    college_name VARCHAR(180) NOT NULL,
    recipient_email VARCHAR(255),
    certificate_number VARCHAR(48) NOT NULL,
    public_token VARCHAR(64) NOT NULL,
    pdf_path VARCHAR(512),
    status VARCHAR(16) NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_certificate_record PRIMARY KEY (id),
    CONSTRAINT fk_certificate_record_batch_id_certificate_batch FOREIGN KEY(batch_id) REFERENCES certificate_batch (id) ON DELETE CASCADE,
    CONSTRAINT fk_certificate_record_submission_id_submission FOREIGN KEY(submission_id) REFERENCES submission (id) ON DELETE SET NULL,
    CONSTRAINT uq_certificate_record_certificate_number UNIQUE (certificate_number),
    CONSTRAINT uq_certificate_record_public_token UNIQUE (public_token)
);

CREATE INDEX ix_certificate_record_batch_id ON certificate_record (batch_id);

CREATE UNIQUE INDEX ix_certificate_record_submission_id ON certificate_record (submission_id);

ALTER TABLE form ADD COLUMN confirmation_format VARCHAR(12) NOT NULL DEFAULT 'text';

ALTER TABLE form ADD COLUMN closed_at DATETIME;

ALTER TABLE form ADD COLUMN closed_message TEXT;

ALTER TABLE form ADD COLUMN parent_form_id INTEGER;

CREATE UNIQUE INDEX ix_form_parent_form_id ON form (parent_form_id);

ALTER TABLE form ADD CONSTRAINT fk_form_parent_form_id_form FOREIGN KEY(parent_form_id) REFERENCES form (id) ON DELETE CASCADE;

UPDATE alembic_version SET version_num='f45559f86783' WHERE alembic_version.version_num = 'd6fd79910711';

-- Running upgrade f45559f86783 -> c84a1f2d9e30

ALTER TABLE form ADD COLUMN event_start_at DATETIME;

ALTER TABLE form ADD COLUMN event_end_at DATETIME;

ALTER TABLE form ADD COLUMN event_timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata';

ALTER TABLE form ADD COLUMN event_location VARCHAR(255);

ALTER TABLE certificate_record ADD COLUMN notification_status VARCHAR(16) NOT NULL DEFAULT 'skipped';

UPDATE alembic_version SET version_num='c84a1f2d9e30' WHERE alembic_version.version_num = 'f45559f86783';
