import mimetypes
from io import BytesIO
from xml.sax.saxutils import escape

import pandas as pd
from flask import current_app
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import joinedload, selectinload

from ..models import Alert, LogEntry, utcnow
from ..utils import rule_names, scoped


def stamp(value):
    # readable timestamp for exports
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def alerts_frame():
    # alert rows with the latest analyst note
    limit = current_app.config["REPORT_MAX_ROWS"]
    names = rule_names()
    query = scoped(Alert.query, Alert).options(selectinload(Alert.notes), joinedload(Alert.resolver))
    rows = []
    for alert in query.order_by(Alert.event_time.desc()).limit(limit):
        notes = [n for n in alert.notes if n.body]
        rows.append({
            "ID": alert.id, "Event time": stamp(alert.event_time), "IP": alert.ip,
            "Type": names.get(alert.type, alert.type), "Severity": alert.severity, "Status": alert.status,
            "Description": alert.description, "Resolution note": notes[-1].body if notes else "",
            "Closed by": alert.resolver.name if alert.resolver else "",
        })
    return pd.DataFrame(rows)


def logs_frame():
    # parsed entry rows
    limit = current_app.config["REPORT_MAX_ROWS"]
    query = scoped(LogEntry.query, LogEntry).options(joinedload(LogEntry.log))
    rows = [{
        "ID": e.id, "Timestamp": stamp(e.timestamp), "IP": e.ip, "Method": e.method, "Status": e.status_code,
        "Request": e.request, "Source file": e.log.filename,
    } for e in query.order_by(LogEntry.timestamp.desc()).limit(limit)]
    return pd.DataFrame(rows)


FRAMES = {"alerts": alerts_frame, "logs": logs_frame}


def to_pdf(frame, title, author):
    # landscape table report
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=28, bottomMargin=28, title=title)
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7, leading=9)
    head = ParagraphStyle("head", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    shown = frame.head(current_app.config["PDF_MAX_ROWS"])
    meta = f"Generated {stamp(utcnow())} UTC by {escape(author)} - {len(shown)} of {len(frame)} rows"
    story = [Paragraph(escape(title), styles["Title"]), Paragraph(meta, styles["Normal"]), Spacer(1, 12)]
    if shown.empty:
        story.append(Paragraph("No data available.", styles["Normal"]))
    else:
        data = [[Paragraph(escape(str(col)), head) for col in shown.columns]]
        data += [[Paragraph(escape(str(v)[:160]), cell) for v in row] for row in shown.itertuples(index=False)]
        weights = [max(8, len(str(c)), min(int(shown[c].astype(str).str.len().max()), 50)) for c in shown.columns]
        widths = [doc.width * w / sum(weights) for w in weights]
        table = Table(data, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2446e8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f8")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d5dae4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
    doc.build(story)
    buffer.seek(0)
    return buffer


def to_xlsx(frame, sheet):
    # excel workbook with styled header and sized columns
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet)
        sheet_obj = writer.sheets[sheet]
        for cell in sheet_obj[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2446E8")
        for column in sheet_obj.columns:
            size = max(len(str(c.value or "")) for c in column[:200])
            sheet_obj.column_dimensions[column[0].column_letter].width = min(size + 2, 60)
    buffer.seek(0)
    return buffer


def build(dataset, fmt, author):
    # returns file buffer, filename and mimetype plus the row count
    frame = FRAMES[dataset]()
    name = f"cyberwatch_{dataset}_{utcnow().strftime('%Y%m%d_%H%M%S')}.{fmt}"
    if fmt == "pdf":
        buffer = to_pdf(frame, f"CyberWatch {dataset} report", author)
    elif fmt == "xlsx":
        buffer = to_xlsx(frame, dataset.title())
    else:
        buffer = BytesIO(frame.to_csv(index=False).encode("utf-8-sig"))
    return buffer, name, mimetypes.guess_type(name)[0] or "application/octet-stream", len(frame)
