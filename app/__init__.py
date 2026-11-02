import os

from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()

from config import Config
from app.extensions import csrf, db, limiter, login_manager, migrate


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    elif not app.config.get("SECRET_KEY"):
        raise RuntimeError("Set SECRET_KEY before starting the application.")

    # Must run before db.init_app(): Flask-SQLAlchemy builds the engine there.
    # QueuePool-only options crash SQLite's StaticPool, so add them for MySQL only.
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("mysql"):
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

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(forms)
    app.register_blueprint(organization)

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
