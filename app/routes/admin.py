import os
import re
from collections import Counter
from datetime import timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from config import DEFAULTS

from ..extensions import db
from ..models import ActivityLog, Alert, DetectionRule, LogEntry, UploadedLog, User, utcnow
from ..utils import admin_required, log_activity

bp = Blueprint("admin", __name__, url_prefix="/admin")


def grouped(column, *filters):
    # count rows per value of a column
    query = db.session.query(column, func.count())
    for item in filters:
        query = query.filter(item)
    return dict(query.group_by(column).all())


@bp.route("/")
@admin_required
def overview():
    # how the whole system is behaving
    cfg = current_app.config
    statuses = grouped(Alert.status)
    severities = grouped(Alert.severity)
    uploads_by_user = grouped(UploadedLog.user_id)
    alerts_by_user = grouped(Alert.user_id)
    closed_by_user = grouped(Alert.user_id, Alert.status.in_(DEFAULTS["closing_statuses"]))
    analysts = []
    for user in User.query.order_by(User.name).all():
        total = alerts_by_user.get(user.id, 0)
        closed = closed_by_user.get(user.id, 0)
        analysts.append({"user": user, "uploads": uploads_by_user.get(user.id, 0), "alerts": total, "closed": closed, "open": total - closed})
    closed_rows = db.session.query(Alert.created_at, Alert.resolved_at).filter(Alert.resolved_at.isnot(None)).all()
    spans = [(end - start).total_seconds() for start, end in closed_rows if start and end]
    total_alerts = sum(statuses.values())
    closed_total = sum(statuses.get(s, 0) for s in DEFAULTS["closing_statuses"])
    folder = cfg["UPLOAD_FOLDER"]
    disk = sum(os.path.getsize(os.path.join(folder, f)) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)))
    since = utcnow() - timedelta(days=cfg["TREND_DAYS"])
    per_day = Counter(row[0].date() for row in db.session.query(UploadedLog.upload_date).filter(UploadedLog.upload_date >= since))
    days = sorted(per_day)
    health = {
        "users": User.query.count(), "active_users": User.query.filter_by(active=True).count(),
        "uploads": UploadedLog.query.count(), "failed_uploads": UploadedLog.query.filter_by(status="failed").count(),
        "entries": LogEntry.query.count(), "alerts": total_alerts, "closed": closed_total,
        "resolution_rate": round(100 * closed_total / total_alerts) if total_alerts else 0,
        "avg_close_hours": round(sum(spans) / len(spans) / 3600, 1) if spans else 0,
        "rules_on": DetectionRule.query.filter_by(enabled=True).count(), "rules": DetectionRule.query.count(),
        "database": db.engine.dialect.name, "disk_mb": round(disk / (1024 * 1024), 2),
    }
    charts = {
        "statuses": {"labels": [DEFAULTS["alert_statuses"][k] for k in DEFAULTS["alert_statuses"]], "values": [statuses.get(k, 0) for k in DEFAULTS["alert_statuses"]], "keys": list(DEFAULTS["alert_statuses"])},
        "severities": {"labels": list(DEFAULTS["severity_weights"]), "values": [severities.get(k, 0) for k in DEFAULTS["severity_weights"]]},
        "analysts": {"labels": [a["user"].name for a in analysts], "open": [a["open"] for a in analysts], "closed": [a["closed"] for a in analysts]},
        "uploads": {"labels": [d.strftime("%d %b") for d in days], "values": [per_day[d] for d in days]},
    }
    recent = ActivityLog.query.order_by(ActivityLog.id.desc()).limit(12).all()
    return render_template("admin/overview.html", health=health, charts=charts, analysts=analysts, recent=recent)


@bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    # list accounts and add new ones
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password, role = request.form.get("password", ""), request.form.get("role")
        minimum = current_app.config["MIN_PASSWORD_LENGTH"]
        if not name or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or role not in DEFAULTS["roles"]:
            flash("Enter a name, a valid email and a role.", "danger")
        elif len(password) < minimum:
            flash(f"Password needs at least {minimum} characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("A user with that email already exists.", "danger")
        else:
            user = User(name=name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            log_activity("user_created", f"{email} as {role}")
            db.session.commit()
            flash(f"{name} can now sign in.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/users.html", users=User.query.order_by(User.created_at.desc()).all())


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    # enable or disable an account
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot disable your own account.", "danger")
    else:
        user.active = not user.active
        log_activity("user_enabled" if user.active else "user_disabled", user.email)
        db.session.commit()
        flash(f"{user.name} is now {'active' if user.active else 'disabled'}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/password", methods=["POST"])
@admin_required
def reset_password(user_id):
    # set a new password for a user
    user = db.get_or_404(User, user_id)
    password = request.form.get("password", "")
    if len(password) < current_app.config["MIN_PASSWORD_LENGTH"]:
        flash("Password is too short.", "danger")
    else:
        user.set_password(password)
        log_activity("password_reset", user.email)
        db.session.commit()
        flash(f"Password updated for {user.name}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/rules", methods=["GET", "POST"])
@admin_required
def rules():
    # tune detection rules
    if request.method == "POST":
        rule = db.get_or_404(DetectionRule, request.form.get("rule_id", type=int))
        severity = request.form.get("severity")
        threshold = request.form.get("threshold", type=int)
        window = request.form.get("window_seconds", type=int)
        pattern = request.form.get("pattern", "")
        try:
            for line in pattern.splitlines():
                if line.strip():
                    re.compile(line.strip())
        except re.error as exc:
            flash(f"Invalid pattern: {exc}", "danger")
            return redirect(url_for("admin.rules"))
        if severity not in DEFAULTS["severity_weights"] or not threshold or threshold < 1 or window is None or window < 0:
            flash("Check severity, threshold and window values.", "danger")
            return redirect(url_for("admin.rules"))
        rule.severity, rule.threshold, rule.window_seconds = severity, threshold, window
        rule.enabled = bool(request.form.get("enabled"))
        if rule.kind == "pattern":
            rule.pattern = pattern.strip()
        log_activity("rule_updated", f"{rule.key} enabled={rule.enabled}")
        db.session.commit()
        flash(f"{rule.name} saved. New uploads will use it.", "success")
        return redirect(url_for("admin.rules"))
    return render_template("admin/rules.html", rules=DetectionRule.query.order_by(DetectionRule.id).all())


@bp.route("/activity")
@admin_required
def activity():
    # full audit trail
    page = request.args.get("page", 1, type=int)
    query = ActivityLog.query.order_by(ActivityLog.id.desc())
    return render_template("admin/activity.html", pagination=query.paginate(page=page, per_page=current_app.config["PAGE_SIZE"], error_out=False))
