-- Forms Gamkers database schema for phpMyAdmin import (no SSH access).
-- Target: MySQL 5.7.8+ or MariaDB 10.2.7+ (InnoDB). Alembic revision: d6fd79910711.
-- Import ONCE into an EMPTY database: phpMyAdmin > select database > Import.
-- Generated with: flask --app wsgi db upgrade --sql (mysql+pymysql DATABASE_URL).
-- Do not edit by hand. Regenerate whenever a new migration is added.

SET NAMES utf8mb4;
ALTER DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
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

