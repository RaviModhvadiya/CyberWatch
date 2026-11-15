from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    # naive utc timestamp used by every table
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(UserMixin, db.Model):
    # application accounts for admins and analysts
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="analyst")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login = db.Column(db.DateTime)

    @property
    def is_active(self):
        return self.active

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def initials(self):
        return "".join(part[0] for part in self.name.split()[:2]).upper() or "?"

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


@login_manager.user_loader
def load_user(user_id):
    # restore the session user
    return db.session.get(User, int(user_id))


class UploadedLog(db.Model):
    # one uploaded file and its processing result
    __tablename__ = "uploaded_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(300), nullable=False)
    log_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="queued")
    total_entries = db.Column(db.Integer, default=0)
    skipped_lines = db.Column(db.Integer, default=0)
    alert_count = db.Column(db.Integer, default=0)
    error = db.Column(db.String(300))
    upload_date = db.Column(db.DateTime, default=utcnow, index=True)
    user = db.relationship("User")


class LogEntry(db.Model):
    # one parsed log line
    __tablename__ = "log_entries"
    id = db.Column(db.Integer, primary_key=True)
    log_id = db.Column(db.Integer, db.ForeignKey("uploaded_logs.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    ip = db.Column(db.String(64), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    status_code = db.Column(db.Integer, index=True)
    method = db.Column(db.String(16))
    request = db.Column(db.Text)
    user_agent = db.Column(db.String(255))
    raw = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    log = db.relationship("UploadedLog", backref="entries")


class Alert(db.Model):
    # one detection result tied to a log entry
    __tablename__ = "alerts"
    id = db.Column(db.Integer, primary_key=True)
    log_id = db.Column(db.Integer, db.ForeignKey("uploaded_logs.id"), nullable=False, index=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("log_entries.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    ip = db.Column(db.String(64), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False, index=True)
    severity = db.Column(db.String(16), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    description = db.Column(db.String(400))
    event_time = db.Column(db.DateTime, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    entry = db.relationship("LogEntry", backref="alerts")
    log = db.relationship("UploadedLog", backref="alerts")
    user = db.relationship("User", foreign_keys=[user_id])
    resolver = db.relationship("User", foreign_keys=[resolved_by])
    notes = db.relationship("AlertNote", backref="alert", order_by="AlertNote.id")


class AlertNote(db.Model):
    # analyst note or status change on an alert
    __tablename__ = "alert_notes"
    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.Integer, db.ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text)
    status_to = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=utcnow)
    author = db.relationship("User")


class Report(db.Model):
    # history of generated exports
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    dataset = db.Column(db.String(20), nullable=False)
    fmt = db.Column(db.String(10), nullable=False)
    row_count = db.Column(db.Integer, default=0)
    generated_date = db.Column(db.DateTime, default=utcnow)
    user = db.relationship("User")


class DetectionRule(db.Model):
    # editable detection rule
    __tablename__ = "detection_rules"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    severity = db.Column(db.String(16), nullable=False)
    pattern = db.Column(db.Text)
    threshold = db.Column(db.Integer, default=1)
    window_seconds = db.Column(db.Integer, default=0)
    description = db.Column(db.String(255))
    enabled = db.Column(db.Boolean, nullable=False, default=True)


class ActivityLog(db.Model):
    # audit trail of what happens in the system
    __tablename__ = "activity_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(40), nullable=False, index=True)
    detail = db.Column(db.String(300))
    ip = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    user = db.relationship("User")
