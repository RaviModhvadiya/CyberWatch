import os
from collections import defaultdict
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from config import DEFAULTS

from ..extensions import db
from ..models import Alert, AlertNote, LogEntry, UploadedLog
from ..services.pipeline import process_log
from ..utils import log_activity, rule_names, scoped

bp = Blueprint("logs", __name__, url_prefix="/logs")


@bp.route("/")
@login_required
def index():
    # uploaded files and their processing result
    page = request.args.get("page", 1, type=int)
    query = scoped(UploadedLog.query, UploadedLog).options(joinedload(UploadedLog.user)).order_by(UploadedLog.upload_date.desc())
    return render_template("logs.html", pagination=query.paginate(page=page, per_page=current_app.config["PAGE_SIZE"], error_out=False))


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    # accept a file, parse it and run detection
    cfg = current_app.config
    if request.method == "POST":
        file = request.files.get("logfile")
        log_type = request.form.get("log_type", "auto")
        if not file or not file.filename:
            flash("Choose a log file to upload.", "danger")
            return redirect(url_for("logs.upload"))
        extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if extension not in cfg["ALLOWED_EXTENSIONS"] or log_type not in DEFAULTS["log_types"]:
            flash("Allowed file types: " + ", ".join(sorted(cfg["ALLOWED_EXTENSIONS"])), "danger")
            return redirect(url_for("logs.upload"))
        stored = f"{uuid4().hex}_{secure_filename(file.filename)}"
        path = os.path.join(cfg["UPLOAD_FOLDER"], stored)
        file.save(path)
        log = UploadedLog(user_id=current_user.id, filename=file.filename, stored_name=stored, log_type=log_type, status="queued")
        db.session.add(log)
        db.session.commit()
        process_log(log, path)
        log_activity("log_uploaded", f"{log.filename} ({log.status}, {log.total_entries} entries, {log.alert_count} alerts)")
        db.session.commit()
        if log.status == "completed":
            flash(f"Parsed {log.total_entries} entries and raised {log.alert_count} alerts.", "success")
            return redirect(url_for("logs.entries", log_id=log.id))
        flash(f"Processing failed: {log.error}", "danger")
        return redirect(url_for("logs.index"))
    return render_template("upload.html", max_mb=cfg["MAX_CONTENT_LENGTH"] // (1024 * 1024))


@bp.route("/entries")
@login_required
def entries():
    # searchable explorer of parsed entries
    args = request.args
    query = scoped(LogEntry.query, LogEntry).options(joinedload(LogEntry.log))
    log = None
    if args.get("log_id", type=int):
        log = scoped(UploadedLog.query, UploadedLog).filter_by(id=args.get("log_id", type=int)).first_or_404()
        query = query.filter(LogEntry.log_id == log.id)
    if args.get("ip", "").strip():
        query = query.filter(LogEntry.ip.like(f"%{args['ip'].strip()}%"))
    if args.get("status", type=int) is not None:
        query = query.filter(LogEntry.status_code == args.get("status", type=int))
    if args.get("q", "").strip():
        query = query.filter(LogEntry.request.like(f"%{args['q'].strip()}%"))
    if args.get("flagged"):
        query = query.filter(LogEntry.alerts.any())
    pagination = query.order_by(LogEntry.timestamp.desc(), LogEntry.id.desc()).paginate(
        page=args.get("page", 1, type=int), per_page=current_app.config["PAGE_SIZE"], error_out=False)
    marks = defaultdict(list)
    ids = [entry.id for entry in pagination.items]
    if ids:
        for alert in Alert.query.filter(Alert.entry_id.in_(ids)).all():
            marks[alert.entry_id].append(alert)
    return render_template("entries.html", pagination=pagination, marks=marks, log=log, names=rule_names())


@bp.route("/<int:log_id>/delete", methods=["POST"])
@login_required
def delete(log_id):
    # remove a file with its entries, alerts and notes
    log = scoped(UploadedLog.query, UploadedLog).filter_by(id=log_id).first_or_404()
    alert_ids = db.session.query(Alert.id).filter_by(log_id=log.id)
    AlertNote.query.filter(AlertNote.alert_id.in_(alert_ids)).delete(synchronize_session=False)
    Alert.query.filter_by(log_id=log.id).delete(synchronize_session=False)
    LogEntry.query.filter_by(log_id=log.id).delete(synchronize_session=False)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], log.stored_name)
    log_activity("log_deleted", log.filename)
    db.session.delete(log)
    db.session.commit()
    if os.path.exists(path):
        os.remove(path)
    flash("Log file and its findings were deleted.", "success")
    return redirect(url_for("logs.index"))
