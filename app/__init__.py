import os

from flask import Flask, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from config import DEFAULTS, Config

from .extensions import csrf, db, login_manager
from .models import utcnow


def ensure_database(uri):
    # create the mysql schema when it does not exist yet
    url = make_url(uri)
    if not url.drivername.startswith("mysql"):
        return
    engine = create_engine(url._replace(database=None))
    with engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{url.database}` CHARACTER SET utf8mb4"))
        conn.commit()
    engine.dispose()


def time_ago(value):
    # short relative time for tables
    if not value:
        return "never"
    seconds = int((utcnow() - value).total_seconds())
    if seconds < 45:
        return "just now"
    for limit, unit in ((3600, "min"), (86400, "h"), (86400 * 30, "d")):
        if seconds < limit:
            divisor = {"min": 60, "h": 3600, "d": 86400}[unit]
            return f"{max(seconds // divisor, 1)} {unit} ago"
    return value.strftime("%d %b %Y")


def create_app():
    # application factory
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["INSTANCE_DIR"], exist_ok=True)
    try:
        ensure_database(app.config["SQLALCHEMY_DATABASE_URI"])
    except Exception as exc:
        raise SystemExit(f"Cannot reach the database: {exc}\nStart MySQL in XAMPP or leave DATABASE_URL empty in .env to use SQLite.")

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    app.jinja_env.globals["defaults"] = DEFAULTS
    app.jinja_env.filters["ago"] = time_ago

    from .models import Alert
    from .routes import register_blueprints
    from .seed import seed_admin, seed_rules
    from .utils import scoped

    register_blueprints(app)
    with app.app_context():
        db.create_all()
        seed_rules()
        seed_admin()

    @app.context_processor
    def inject_globals():
        # values every template needs
        pending = 0
        if current_user.is_authenticated:
            pending = scoped(Alert.query, Alert).filter(Alert.status.in_(DEFAULTS["active_statuses"])).count()
        return {"app_name": app.config["APP_NAME"], "pending_alerts": pending}

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def handle_error(error):
        # friendly error page, anonymous visitors go to sign in
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return render_template("error.html", error=error), error.code

    return app
