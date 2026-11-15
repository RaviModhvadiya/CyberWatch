from collections import Counter
from datetime import datetime, time

from flask import current_app
from sqlalchemy import func

from config import DEFAULTS

from ..models import Alert, LogEntry, utcnow
from ..utils import rule_names, scoped


def score_level(score):
    # pick the posture label and colour for a score
    for level in DEFAULTS["score_levels"]:
        if score <= level["max"]:
            return level
    return DEFAULTS["score_levels"][-1]


def summary():
    # numbers shown on the dashboard cards
    cfg = current_app.config
    entries = scoped(LogEntry.query, LogEntry)
    active = scoped(Alert.query, Alert).filter(Alert.status.in_(DEFAULTS["active_statuses"]))
    by_severity = dict(active.with_entities(Alert.severity, func.count(Alert.id)).group_by(Alert.severity).all())
    weighted = sum(DEFAULTS["severity_weights"].get(name, 0) * count for name, count in by_severity.items())
    risky = active.with_entities(Alert.ip).group_by(Alert.ip).having(func.count(Alert.id) >= cfg["HIGH_RISK_ALERTS"]).count()
    start = datetime.combine(utcnow().date(), time.min)
    return {
        "total_logs": entries.count(),
        "today_logs": entries.filter(LogEntry.created_at >= start).count(),
        "failed_logins": entries.filter(LogEntry.status_code == cfg["FAILED_STATUS"]).count(),
        "success_logins": entries.filter(LogEntry.status_code.between(cfg["SUCCESS_MIN"], cfg["SUCCESS_MAX"])).count(),
        "critical_alerts": by_severity.get("critical", 0),
        "high_risk_ips": risky,
        "attack_score": round(100 * weighted / (weighted + cfg["SCORE_SCALE"])) if weighted else 0,
    }


def charts(cards):
    # series for the five dashboard charts
    cfg = current_app.config
    entries = scoped(LogEntry.query, LogEntry)
    alerts = scoped(Alert.query, Alert)
    hours = Counter(row[0].hour for row in entries.filter(LogEntry.status_code == cfg["FAILED_STATUS"]).with_entities(LogEntry.timestamp))
    top = alerts.with_entities(Alert.ip, func.count(Alert.id)).group_by(Alert.ip).order_by(func.count(Alert.id).desc()).limit(cfg["TOP_IP_LIMIT"]).all()
    names = rule_names()
    types = alerts.with_entities(Alert.type, func.count(Alert.id)).group_by(Alert.type).order_by(func.count(Alert.id).desc()).all()
    days = Counter(row[0].date() for row in alerts.with_entities(Alert.event_time) if row[0])
    keys = sorted(days)[-cfg["TREND_DAYS"]:]
    return {
        "failed_per_hour": {"labels": [f"{h:02d}:00" for h in range(24)], "values": [hours.get(h, 0) for h in range(24)]},
        "top_ips": {"labels": [row[0] for row in top], "values": [row[1] for row in top]},
        "attack_types": {"labels": [names.get(row[0], row[0]) for row in types], "values": [row[1] for row in types], "keys": [row[0] for row in types]},
        "login_split": {"labels": ["Failed", "Successful"], "values": [cards["failed_logins"], cards["success_logins"]]},
        "daily_trend": {"labels": [k.strftime("%d %b") for k in keys], "values": [days[k] for k in keys]},
    }


def dashboard_payload():
    # everything the dashboard and its refresh endpoint need
    cards = summary()
    return {"cards": cards, "score": score_level(cards["attack_score"]), "charts": charts(cards)}
