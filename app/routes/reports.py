from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from config import DEFAULTS

from ..extensions import db
from ..models import Report
from ..services import reports as builder
from ..utils import log_activity, scoped

bp = Blueprint("reports", __name__, url_prefix="/reports")


def deliver(dataset, fmt):
    # build the file, record it and send it as a download
    buffer, name, mimetype, count = builder.build(dataset, fmt, current_user.name)
    db.session.add(Report(user_id=current_user.id, dataset=dataset, fmt=fmt, row_count=count))
    log_activity("report_generated", f"{dataset} as {fmt} ({count} rows)")
    db.session.commit()
    return send_file(buffer, as_attachment=True, download_name=name, mimetype=mimetype)


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    # choose a dataset and format, then download
    if request.method == "POST":
        dataset, fmt = request.form.get("dataset"), request.form.get("fmt")
        if dataset not in DEFAULTS["report_datasets"] or fmt not in DEFAULTS["report_formats"]:
            flash("Pick a valid dataset and format.", "danger")
            return redirect(url_for("reports.index"))
        return deliver(dataset, fmt)
    history = scoped(Report.query, Report).order_by(Report.generated_date.desc()).limit(15).all()
    return render_template("reports.html", history=history)


@bp.route("/<int:report_id>/again", methods=["POST"])
@login_required
def again(report_id):
    # regenerate a past export with current data
    report = scoped(Report.query, Report).filter_by(id=report_id).first_or_404()
    return deliver(report.dataset, report.fmt)
