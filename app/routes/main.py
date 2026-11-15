from flask import Blueprint, current_app, jsonify, redirect, render_template, url_for
from flask_login import login_required

from config import DEFAULTS

from ..models import Alert
from ..services import stats
from ..utils import rule_names, scoped, severity_order

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    # landing redirect
    return redirect(url_for("main.dashboard"))


@bp.route("/dashboard")
@login_required
def dashboard():
    # summary cards, charts and the alerts that need attention
    urgent = (
        scoped(Alert.query, Alert).filter(Alert.status.in_(DEFAULTS["active_statuses"]))
        .order_by(severity_order().desc(), Alert.id.desc()).limit(7).all()
    )
    return render_template(
        "dashboard.html", payload=stats.dashboard_payload(), urgent=urgent,
        names=rule_names(), refresh=current_app.config["REFRESH_SECONDS"],
    )


@bp.route("/api/dashboard")
@login_required
def api_dashboard():
    # json used by the live refresh
    return jsonify(stats.dashboard_payload())
