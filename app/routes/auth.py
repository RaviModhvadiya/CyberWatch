from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User, utcnow
from ..utils import log_activity, safe_next

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    # sign in with email and password
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.active and user.check_password(request.form.get("password", "")):
            login_user(user, remember=bool(request.form.get("remember")))
            user.last_login = utcnow()
            log_activity("login", user.email, user)
            db.session.commit()
            return redirect(safe_next(request.args.get("next"), url_for("main.dashboard")))
        log_activity("login_failed", email)
        db.session.commit()
        flash("Email or password is incorrect, or the account is disabled.", "danger")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    # end the session
    log_activity("logout", current_user.email)
    db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    # edit own name and password
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        new_password = request.form.get("new_password", "")
        if not name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("auth.profile"))
        if new_password:
            if not current_user.check_password(request.form.get("current_password", "")):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("auth.profile"))
            if len(new_password) < current_app.config["MIN_PASSWORD_LENGTH"]:
                flash(f"New password needs at least {current_app.config['MIN_PASSWORD_LENGTH']} characters.", "danger")
                return redirect(url_for("auth.profile"))
            current_user.set_password(new_password)
        current_user.name = name
        log_activity("profile_updated", current_user.email)
        db.session.commit()
        flash("Profile saved.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("profile.html")
