import re
from collections import Counter
from datetime import datetime, timedelta

import pandas as pd
from flask import current_app

from config import DEFAULTS

WEB_LINE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "(?P<req>[^"]*)" (?P<status>\d{3}) \S+'
    r'(?: "[^"]*" "(?P<ua>[^"]*)")?'
)
SSH_LINE = re.compile(
    r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2}) (?P<time>\d{2}:\d{2}:\d{2}) \S+ sshd\[\d+\]: "
    r"(?P<msg>(?P<result>Failed|Accepted) \w+ for (?:invalid user )?(?P<user>\S+) from (?P<ip>[0-9a-fA-F.:]+).*)"
)
WIN_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\S*\s+(?:EventID[=:]\s*)?(?P<event>\d{3,5})\b(?P<rest>.*?)"
    r"(?:IpAddress|Source Network Address)\s*[=:]\s*(?P<ip>[0-9a-fA-F.:]+)",
    re.IGNORECASE,
)


def make_row(ip, timestamp, status, method, request, agent, raw):
    # normalise one parsed line to the entry columns
    return {
        "ip": str(ip)[:64], "timestamp": timestamp, "status_code": status, "method": (method or "")[:16],
        "request": request or "", "user_agent": (agent or "")[:255], "raw": (raw or "")[:2000],
    }


def parse_web(line):
    # apache and nginx combined format
    match = WEB_LINE.match(line)
    if not match:
        return None
    parts = match.group("req").split(" ", 2)
    method, target = (parts[0], parts[1]) if len(parts) > 1 else ("", match.group("req"))
    stamp = datetime.strptime(match.group("ts").split(" ")[0], "%d/%b/%Y:%H:%M:%S")
    return make_row(match.group("ip"), stamp, int(match.group("status")), method, target, match.group("ua"), line)


def parse_ssh(line):
    # openssh auth log
    match = SSH_LINE.match(line)
    if not match:
        return None
    now = datetime.now()
    stamp = datetime.strptime(f"{now.year} {match['mon']} {match['day']} {match['time']}", "%Y %b %d %H:%M:%S")
    if stamp > now + timedelta(days=1):
        stamp = stamp.replace(year=now.year - 1)
    cfg = current_app.config
    status = cfg["FAILED_STATUS"] if match["result"] == "Failed" else cfg["SUCCESS_MIN"]
    return make_row(match["ip"], stamp, status, "SSH", match["msg"], "", line)


def parse_windows(line):
    # windows security events exported as text
    match = WIN_LINE.match(line)
    outcome = DEFAULTS["windows_events"].get(match["event"]) if match else None
    if not outcome:
        return None
    cfg = current_app.config
    status = cfg["FAILED_STATUS"] if outcome == "failed" else cfg["SUCCESS_MIN"]
    stamp = datetime.fromisoformat(match["ts"].replace("T", " "))
    return make_row(match["ip"], stamp, status, "WIN", f"EventID {match['event']} {match['rest'].strip()}", "", line)


LINE_PARSERS = {"apache": parse_web, "nginx": parse_web, "ssh": parse_ssh, "windows": parse_windows}
AUTO_ORDER = ["apache", "ssh", "windows"]


def resolve_columns(columns):
    # map csv headers to canonical fields using the alias table
    lowered = {str(col).strip().lower(): col for col in columns}
    mapping = {}
    for field, names in DEFAULTS["csv_aliases"].items():
        for name in names:
            if name in lowered:
                mapping[field] = lowered[name]
                break
    return mapping


def parse_csv(path):
    # csv exports with flexible column names
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    mapping = resolve_columns(frame.columns)
    missing = [field for field in ("ip", "timestamp") if field not in mapping]
    if missing:
        raise ValueError("CSV is missing required column(s): " + ", ".join(missing))
    stamps = pd.to_datetime(frame[mapping["timestamp"]], errors="coerce", utc=True, format="mixed").dt.tz_localize(None)
    status = pd.to_numeric(frame[mapping["status_code"]], errors="coerce") if "status_code" in mapping else None
    spare = [col for col in frame.columns if col not in mapping.values()]
    rows, skipped = [], 0
    for index, record in frame.iterrows():
        stamp = stamps.iloc[index] if hasattr(stamps, "iloc") else None
        if pd.isna(stamp) or not str(record[mapping["ip"]]).strip():
            skipped += 1
            continue
        if "request" in mapping:
            request = record[mapping["request"]]
        else:
            request = " ".join(f"{col}={record[col]}" for col in spare)
        code = None if status is None or pd.isna(status.iloc[index]) else int(status.iloc[index])
        rows.append(make_row(
            record[mapping["ip"]].strip(), stamp.to_pydatetime(), code,
            record[mapping["method"]] if "method" in mapping else "", request,
            record[mapping["user_agent"]] if "user_agent" in mapping else "", ",".join(map(str, record.values)),
        ))
    return rows, skipped


def parse_file(path, log_type):
    # returns parsed rows, skipped line count and the detected type
    if log_type == "csv" or (log_type == "auto" and path.lower().endswith(".csv")):
        rows, skipped = parse_csv(path)
        return rows, skipped, "csv"
    names = [log_type] if log_type in LINE_PARSERS else AUTO_ORDER
    rows, skipped, hits = [], 0, Counter()
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            for name in names:
                try:
                    row = LINE_PARSERS[name](line)
                except ValueError:
                    row = None
                if row:
                    rows.append(row)
                    hits[name] += 1
                    break
            else:
                skipped += 1
    detected = log_type if log_type != "auto" else (hits.most_common(1)[0][0] if hits else "auto")
    return rows, skipped, detected
