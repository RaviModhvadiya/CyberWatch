import re
from collections import defaultdict
from datetime import timedelta
from urllib.parse import unquote_plus

from flask import current_app

from ..extensions import db
from ..models import Alert, DetectionRule


def make_alert(rule, log, entry, description):
    # build one alert row tied to a log entry
    return Alert(
        log_id=log.id, entry_id=entry.id, user_id=log.user_id, ip=entry.ip, type=rule.key,
        severity=rule.severity, status="open", description=description[:400], event_time=entry.timestamp,
    )


def by_status(rule, log, entries):
    # one alert per failed login event
    failed = current_app.config["FAILED_STATUS"]
    return [make_alert(rule, log, e, f"Failed login (HTTP {failed}) from {e.ip}") for e in entries if e.status_code == failed]


def sliding(rule, log, items, label):
    # emit an alert whenever threshold events fall inside the window, then restart the count
    items.sort(key=lambda e: e.timestamp)
    window = timedelta(seconds=rule.window_seconds)
    alerts, left = [], 0
    for right, item in enumerate(items):
        while item.timestamp - items[left].timestamp > window:
            left += 1
        if right - left + 1 >= rule.threshold:
            alerts.append(make_alert(rule, log, item, label))
            left = right + 1
    return alerts


def fail_burst(rule, log, entries):
    # repeated failed logins per ip
    failed = current_app.config["FAILED_STATUS"]
    groups = defaultdict(list)
    for entry in entries:
        if entry.status_code == failed:
            groups[entry.ip].append(entry)
    alerts = []
    for ip, items in groups.items():
        alerts += sliding(rule, log, items, f"{rule.threshold} failed logins from {ip} within {rule.window_seconds}s")
    return alerts


def rate(rule, log, entries):
    # too many requests per ip
    groups = defaultdict(list)
    for entry in entries:
        groups[entry.ip].append(entry)
    alerts = []
    for ip, items in groups.items():
        alerts += sliding(rule, log, items, f"{rule.threshold} requests from {ip} within {rule.window_seconds}s")
    return alerts


def by_pattern(rule, log, entries):
    # regex match on the raw and url-decoded request
    parts = [line.strip() for line in (rule.pattern or "").splitlines() if line.strip()]
    if not parts:
        return []
    try:
        regex = re.compile("|".join(f"(?:{part})" for part in parts), re.IGNORECASE)
    except re.error:
        return []
    alerts = []
    for entry in entries:
        text = entry.request or ""
        if regex.search(text) or regex.search(unquote_plus(text)):
            alerts.append(make_alert(rule, log, entry, f"{rule.name} pattern from {entry.ip}: {text[:140]}"))
    return alerts


HANDLERS = {"status": by_status, "fail_burst": fail_burst, "pattern": by_pattern, "rate": rate}


def run_detection(log, entries):
    # apply every enabled rule to the parsed entries
    alerts = []
    for rule in DetectionRule.query.filter_by(enabled=True).all():
        handler = HANDLERS.get(rule.kind)
        if handler:
            alerts += handler(rule, log, entries)
    db.session.add_all(alerts)
    return alerts
