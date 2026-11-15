from functools import wraps

from flask import abort, request
from flask_login import current_user, login_required
from sqlalchemy import case

from config import DEFAULTS

from .extensions import db
from .models import ActivityLog, Alert, DetectionRule

def admin_required(view):
    # allow administrators only
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def scoped(query, model):
    # analysts only see their own rows, admins see everything
    if current_user.is_admin:
        return query
    return query.filter(model.user_id == current_user.id)


def severity_order():
    # sql expression that ranks alerts by severity weight
    weights = DEFAULTS["severity_weights"]
    return case(*[(Alert.severity == name, weight) for name, weight in weights.items()], else_=0)


def rule_names():
    # map rule keys to display names
    return {rule.key: rule.name for rule in DetectionRule.query.all()}


def log_activity(action, detail="", user=None):
    # queue an audit row in the current session
    actor = user or (current_user if current_user.is_authenticated else None)
    db.session.add(ActivityLog(
        user_id=actor.id if actor else None, action=action, detail=(detail or "")[:300], ip=request.remote_addr,
    ))


def safe_next(target, fallback):
    # accept only local redirect targets
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return fallback
