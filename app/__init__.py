import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template
from sqlalchemy.engine import URL

load_dotenv()

from config import Config
from app.extensions import csrf, db, limiter, login_manager, migrate


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY") and not app.config.get("TESTING"):
        raise RuntimeError("Set SECRET_KEY before starting the application.")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        database_settings = {
            "DB_HOST": app.config.get("DB_HOST"),
            "DB_PORT": app.config.get("DB_PORT"),
            "DB_NAME": app.config.get("DB_NAME"),
            "DB_USER": app.config.get("DB_USER"),
            "DB_PASSWORD": app.config.get("DB_PASSWORD"),
        }
        missing_settings = [
            name for name, value in database_settings.items() if value in (None, "")
        ]
        if missing_settings:
            raise RuntimeError(
                "Set the MySQL settings in .env: " + ", ".join(missing_settings) + "."
            )
        try:
            database_port = int(database_settings["DB_PORT"])
        except (TypeError, ValueError) as error:
            raise RuntimeError("DB_PORT must be a valid TCP port number.") from error
        if not 1 <= database_port <= 65535:
            raise RuntimeError("DB_PORT must be between 1 and 65535.")
        app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
            drivername="mysql+pymysql",
            username=database_settings["DB_USER"],
            password=database_settings["DB_PASSWORD"],
            host=database_settings["DB_HOST"],
            port=database_port,
            database=database_settings["DB_NAME"],
            query={"charset": "utf8mb4"},
        )
    if not app.config.get("CERTIFICATE_STORAGE_PATH"):
        app.config["CERTIFICATE_STORAGE_PATH"] = str(
            Path(app.instance_path) / "certificates"
        )
    if not app.config.get("EMAIL_CSS_PATH"):
        app.config["EMAIL_CSS_PATH"] = str(
            Path(app.static_folder) / "css" / "app.css"
        )

    # Must run before db.init_app(): Flask-SQLAlchemy builds the engine there.
    # QueuePool-only options crash SQLite's StaticPool, so add them for MySQL only.
    database_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    database_driver = getattr(
        database_uri, "drivername", str(database_uri).split(":", 1)[0]
    )
    if database_driver.startswith("mysql"):
        engine_options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
        engine_options.setdefault("pool_size", 5)
        engine_options.setdefault("max_overflow", 5)
        engine_options.setdefault("pool_timeout", 20)
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from app import models
    from app.auth.routes import auth
    from app.forms.routes import forms
    from app.main.routes import main
    from app.organization.routes import organization
    from app.certificates.routes import certificates

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(forms)
    app.register_blueprint(organization)
    app.register_blueprint(certificates)

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; object-src 'none'",
        )
        return response

    @app.context_processor
    def inject_template_globals():
        from datetime import datetime, timezone

        return {"current_year": datetime.now(timezone.utc).year}

    @app.errorhandler(413)
    def request_too_large(_error):
        return render_template("errors/413.html"), 413

    return app
