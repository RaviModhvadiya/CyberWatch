from sqlalchemy import func
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from config import DEFAULTS

from ..extensions import db
from ..models import Alert, AlertNote, DetectionRule, LogEntry, utcnow
from ..utils import log_activity, rule_names, scoped, severity_order

bp = Blueprint("alerts", __name__, url_prefix="/alerts")


@bp.route("/")
@login_required
def index():
    # filterable alert queue, most severe first
    args = request.args
    query = scoped(Alert.query, Alert)
    for field in ("status", "severity", "type"):
        if args.get(field):
            query = query.filter(getattr(Alert, field) == args[field])
    for field in ("entry_id", "log_id"):
        if args.get(field, type=int):
            query = query.filter(getattr(Alert, field) == args.get(field, type=int))
    if args.get("ip", "").strip():
        query = query.filter(Alert.ip.like(f"%{args['ip'].strip()}%"))
    pagination = query.order_by(severity_order().desc(), Alert.id.desc()).paginate(
        page=args.get("page", 1, type=int), per_page=current_app.config["PAGE_SIZE"], error_out=False)
    base = scoped(Alert.query, Alert)
    for field in ("severity", "type"):
        if args.get(field):
            base = base.filter(getattr(Alert, field) == args[field])
    counts = dict(base.with_entities(Alert.status, func.count(Alert.id)).group_by(Alert.status).all())
    return render_template("alerts.html", pagination=pagination, names=rule_names(), counts=counts, total=sum(counts.values()),
                           rules=DetectionRule.query.order_by(DetectionRule.name).all())


@bp.route("/<int:alert_id>")
@login_required
def detail(alert_id):
    # alert with its log entry, nearby activity and notes
    alert = scoped(Alert.query, Alert).filter_by(id=alert_id).first_or_404()
    entry = alert.entry
    nearby = (
        LogEntry.query.filter(LogEntry.log_id == alert.log_id, LogEntry.ip == alert.ip, LogEntry.timestamp <= entry.timestamp)
        .order_by(LogEntry.timestamp.desc(), LogEntry.id.desc()).limit(current_app.config["CONTEXT_ROWS"]).all()
    )
    siblings = scoped(Alert.query, Alert).filter(
        Alert.log_id == alert.log_id, Alert.ip == alert.ip, Alert.id != alert.id,
        Alert.status.in_(DEFAULTS["active_statuses"])).count()
    return render_template("alert_detail.html", alert=alert, entry=entry, nearby=list(reversed(nearby)), siblings=siblings, names=rule_names())


@bp.route("/<int:alert_id>/update", methods=["POST"])
@login_required
def update(alert_id):
    # add a note and or change the status, optionally for every open alert from the same ip
    alert = scoped(Alert.query, Alert).filter_by(id=alert_id).first_or_404()
    status = request.form.get("status", alert.status)
    body = request.form.get("note", "").strip()
    if status not in DEFAULTS["alert_statuses"]:
        flash("Unknown status.", "danger")
        return redirect(url_for("alerts.detail", alert_id=alert.id))
    if status in DEFAULTS["closing_statuses"] and status != alert.status and not body:
        flash("Describe how this was handled before closing the alert.", "danger")
        return redirect(url_for("alerts.detail", alert_id=alert.id))
    if status == alert.status and not body:
        flash("Write a note or choose a new status.", "info")
        return redirect(url_for("alerts.detail", alert_id=alert.id))
    targets = [alert]
    if request.form.get("apply_ip"):
        targets += scoped(Alert.query, Alert).filter(
            Alert.log_id == alert.log_id, Alert.ip == alert.ip, Alert.id != alert.id,
            Alert.status.in_(DEFAULTS["active_statuses"])).all()
    closing = status in DEFAULTS["closing_statuses"]
    for target in targets:
        changed = target.status != status
        target.status = status
        target.resolved_at, target.resolved_by = (utcnow(), current_user.id) if closing else (None, None)
        db.session.add(AlertNote(alert_id=target.id, user_id=current_user.id, body=body or None, status_to=status if changed else None))
    log_activity("alert_updated", f"#{alert.id} -> {status} ({len(targets)} alert(s))")
    db.session.commit()
    flash(f"Updated {len(targets)} alert(s).", "success")
    return redirect(url_for("alerts.detail", alert_id=alert.id))
