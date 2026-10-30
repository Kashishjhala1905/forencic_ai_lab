"""PDF metadata and structure inspection (indicators only)."""
import re
from collections import Counter
from datetime import datetime, timedelta

from .common import finding, not_applicable

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf

IMAGE_EDITORS = re.compile(r"photoshop|gimp|canva|pixlr|picsart|paint\.net|illustrator|inkscape|affinity|corel", re.I)
PDF_EDITORS = re.compile(r"acrobat(?! distiller| pdfmaker)|foxit|phantom|pdf-?xchange|nitro|sejda|ilovepdf|smallpdf|pdfescape|pdf24|pdfsam|pdfelement|wondershare|pdf editor", re.I)


def _pdf_date(s):
    m = re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", s or "")
    if not m:
        return None
    p = [int(x) if x else d for x, d in zip(m.groups(), (1970, 1, 1, 0, 0, 0))]
    try:
        return datetime(*p)
    except ValueError:
        return None


def _family(font: str) -> str:
    f = re.sub(r"^[A-Z]{6}\+", "", font or "")
    return re.split(r"[-,]", f)[0].lower()


def metadata_findings(doc, raw: bytes) -> list[dict]:
    md = doc.metadata or {}
    prod, creator = md.get("producer") or "", md.get("creator") or ""
    created, modified = _pdf_date(md.get("creationDate")), _pdf_date(md.get("modDate"))
    issues, sev = [], "info"
    soft = f"{prod} {creator}"
    if IMAGE_EDITORS.search(soft):
        issues.append(f"Created/modified with image-editing software ({soft.strip()})."); sev = "medium"
    elif PDF_EDITORS.search(soft):
        issues.append(f"Producer is an editing-capable PDF tool ({soft.strip()})."); sev = "low"
    if created and modified:
        if modified < created:
            issues.append("Modification date is earlier than creation date."); sev = "medium"
        elif modified - created > timedelta(days=1):
            issues.append(f"Modified {(modified - created).days} day(s) after creation."); sev = "medium" if sev == "medium" else "low"
    if modified and modified > datetime.now() + timedelta(days=1):
        issues.append("Modification date is in the future."); sev = "medium"
    f1 = finding("pdf_metadata", "PDF metadata inspection", flagged=bool(issues), severity=sev if issues else "info",
                 summary=" ".join(issues) if issues else "No suspicious PDF metadata found." if md else "No PDF metadata present.",
                 details={"producer": prod or None, "creator": creator or None, "author": md.get("author") or None,
                          "title": md.get("title") or None, "created": str(created) if created else None,
                          "modified": str(modified) if modified else None, "pdf_version": md.get("format"), "encrypted": doc.is_encrypted},
                 limitation="PDF metadata is easily rewritten. Legitimate workflows (signing, merging, re-saving) also change it.")
    eofs = raw.count(b"%%EOF")
    f2 = finding("pdf_revisions", "Incremental updates (revisions)", flagged=eofs >= 2, severity="medium" if eofs >= 3 else "low" if eofs == 2 else "info",
                 summary=f"File contains {eofs} revision marker(s); content appended after first save." if eofs >= 2 else "Single revision (no appended updates).",
                 details={"eof_markers": eofs},
                 limitation="Digital signatures, form filling and some scanners also create incremental updates.")
    return [f1, f2]


def structure_findings(doc, raw: bytes) -> list[dict]:
    risky = Counter()
    for x in range(1, min(doc.xref_length(), 5000)):
        try:
            o = doc.xref_object(x, compressed=False)
        except Exception:  # noqa: BLE001
            continue
        for tok in ("/JavaScript", "/Launch", "/EmbeddedFile", "/OpenAction"):
            if tok in o:
                risky[tok] += 1
    ann = Counter()
    fonts, hidden, numeric_spans = Counter(), 0, []
    for page in doc:
        for a in page.annots() or []:
            ann[a.type[1]] += 1
        d = page.get_text("dict")
        for b in d["blocks"]:
            for ln in b.get("lines", []):
                for sp in ln["spans"]:
                    t = sp["text"].strip()
                    if not t:
                        continue
                    fonts[sp["font"]] += len(t)
                    if sp["color"] == 0xFFFFFF and len(t) > 2:
                        hidden += 1
                    if len(re.findall(r"\d", t)) >= 3:
                        numeric_spans.append((_family(sp["font"]), t[:30], page.number + 1))
    out = []
    issues = []
    if risky.get("/JavaScript") or risky.get("/Launch"):
        issues.append("Contains JavaScript or launch actions (never executed by this system).")
    sev = "medium" if issues else "info"
    out.append(finding("pdf_active_content", "Active content & embedded files", flagged=bool(issues), severity=sev,
                       summary=" ".join(issues) if issues else "No JavaScript/launch actions detected." + (" Embedded files present." if risky.get("/EmbeddedFile") else ""),
                       details=dict(risky), limitation="Scans object dictionaries only; content inside compressed object streams may be missed."))
    suspicious_ann = {k: v for k, v in ann.items() if k in ("FreeText", "Redact", "Stamp", "Square")}
    out.append(finding("pdf_annotations", "Annotations & overlays", flagged=bool(suspicious_ann), severity="low" if suspicious_ann else "info",
                       summary=f"Overlay-type annotations present: {dict(suspicious_ann)}." if suspicious_ann else "No overlay-type annotations.",
                       details=dict(ann), limitation="Annotations such as stamps/free text are normal in reviewed documents but can also cover original content."))
    # Fonts: numeric tokens set in a different font family than the page body
    fam = Counter()
    for f, n in fonts.items():
        fam[_family(f)] += n
    nums = Counter(f for f, *_ in numeric_spans)
    body = fam.most_common(1)[0][0] if fam else None
    odd = [s for s in numeric_spans if body and s[0] != body]
    minority = len(numeric_spans) >= 4 and 0 < len(odd) <= max(1, int(0.25 * len(numeric_spans)))
    out.append(finding("pdf_fonts", "Font consistency", flagged=bool(minority or hidden > 0), severity="low" if (minority or hidden) else "info",
                       summary=(f"{len(odd)} numeric text span(s) use a different font family than the document body." if minority else "") +
                               (f" {hidden} white-coloured text span(s) found (possible hidden text)." if hidden else "") or
                       f"{len(fam)} font family(ies); no numeric-font anomaly.",
                       details={"font_families": dict(fam.most_common(8)), "mixed_numeric_spans": [{"text": s[1], "font": s[0], "page": s[2]} for s in odd[:8]],
                                "white_text_spans": hidden},
                       limitation="Bold/italic styling of totals or headers commonly uses other font families; this is a weak indicator."))
    return out


def analyze_pdf(path: str):
    with open(path, "rb") as fh:
        raw = fh.read()
    with pymupdf.open(path) as doc:
        findings = metadata_findings(doc, raw) + structure_findings(doc, raw)
        dims = {"page_count": doc.page_count, "width": int(doc[0].rect.width), "height": int(doc[0].rect.height)}
    findings.append(not_applicable("ela", "Error Level Analysis (ELA)", "ELA applies to JPEG images; this is a PDF (embedded images are not individually analysed)."))
    return findings, None, dims
