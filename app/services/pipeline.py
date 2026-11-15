from ..extensions import db
from ..models import LogEntry
from ..parsers import parse_file
from .detector import run_detection


def process_log(log, path):
    # parse the stored file, save entries and run detection
    try:
        rows, skipped, detected = parse_file(path, log.log_type)
        if not rows:
            raise ValueError("No valid log entries were found in this file")
        entries = [LogEntry(log_id=log.id, user_id=log.user_id, **row) for row in rows]
        db.session.add_all(entries)
        db.session.flush()
        alerts = run_detection(log, entries)
        log.log_type, log.skipped_lines = detected, skipped
        log.total_entries, log.alert_count, log.status = len(entries), len(alerts), "completed"
    except Exception as exc:
        db.session.rollback()
        log.status, log.error = "failed", str(exc)[:290]
    db.session.commit()
    return log
