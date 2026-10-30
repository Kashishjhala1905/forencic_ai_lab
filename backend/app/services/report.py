"""PDF forensic report (ReportLab). All document-derived strings are XML-escaped before rendering."""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..core.config import get_settings

TEAL = colors.HexColor("#0f766e")


def _p(t, st):
    return Paragraph(escape(str(t if t is not None else "—")), st)


def build_report(analysis: dict, document: dict, user: dict) -> Path:
    s = get_settings()
    out = s.storage_path / "reports"; out.mkdir(exist_ok=True)
    path = out / f"{analysis['id']}.pdf"
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.HexColor("#475569"))
    h = ParagraphStyle("h", parent=ss["Heading2"], textColor=TEAL, spaceBefore=10)
    risk = analysis["risk"] or {}
    story = [Paragraph("Forensic AI Lab — Document Analysis Report", ss["Title"]),
             _p(f"File: {document['original_filename']}  |  Analysed: {analysis.get('completed_at')}  |  Requested by: {user['email']}", small), Spacer(1, 6)]
    story.append(Paragraph(f"<b>Outcome: {escape(risk.get('label', 'n/a'))}</b> &nbsp; Risk indicator score: {risk.get('score')}/100 &nbsp; "
                           f"Technical confidence: {risk.get('technical_confidence')}/100", body))
    story.append(_p("The score is a rule-weighted sum of indicators, not a probability of fraud. Technical confidence describes how much evidence "
                    "the system could evaluate and is independent of risk.", small))
    story.append(Paragraph("Key indicators", h))
    contribs = risk.get("contributions") or []
    if contribs:
        data = [["Indicator", "Source", "Severity", "Points", "Explanation"]] + [
            [_p(c["label"], body), c["source"], c["severity"], c["points"], _p(c["explanation"], body)] for c in contribs]
        t = Table(data, colWidths=[40 * mm, 20 * mm, 18 * mm, 14 * mm, 88 * mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
    else:
        story.append(_p("No scored indicators were triggered.", body))
    for r in risk.get("insufficient_reasons", []):
        story.append(_p("Note: " + r, body))
    story.append(Paragraph("Extracted fields", h))
    rows = [["Field", "Value", "Method", "Conf.", "Validation"]]
    for f in (analysis["fields"] or {}).values():
        rows.append([_p(f["label"], body), _p(f["value"], body), f["method"], "—" if f["confidence"] is None else f"{f['confidence']}", f["validation_status"]])
    if len(rows) > 1:
        t = Table(rows, colWidths=[40 * mm, 60 * mm, 36 * mm, 14 * mm, 22 * mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
        story.append(t)
    else:
        story.append(_p("No fields were extracted.", body))
    story.append(Paragraph("Validation results", h))
    for v in analysis["validation"] or []:
        story.append(_p(f"[{v['status'].upper()}] {v['label']} ({v['severity']}): {v['explanation']}", body))
    story.append(Paragraph("Forensic findings", h))
    for f in (analysis["forensic"] or {}).get("findings", []):
        story.append(_p(f"[{f['status'].upper()}{' / FLAGGED' if f['flagged'] else ''}] {f['name']}: {f['summary']}", body))
        if f.get("limitation"):
            story.append(_p("Limitation: " + f["limitation"], small))
    if analysis.get("heatmap_path") and Path(analysis["heatmap_path"]).exists():
        story += [Paragraph("ELA heatmap (bright = larger recompression error; boxes = outlier regions)", h), RLImage(analysis["heatmap_path"], width=120 * mm, height=120 * mm, kind="proportional")]
    ocr = analysis["ocr"] or {}
    story.append(Paragraph("OCR / text extraction", h))
    story.append(_p(f"OCR available: {ocr.get('available')}; OCR used: {ocr.get('used')}; mean confidence: {ocr.get('mean_confidence')}; words: {ocr.get('word_count')}", body))
    story.append(Spacer(1, 10))
    story.append(_p(risk.get("disclaimer", ""), small))
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                      title="Forensic AI Lab Report", author="Forensic AI Lab").build(story)
    return path
