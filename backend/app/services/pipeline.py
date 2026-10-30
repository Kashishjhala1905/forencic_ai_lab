"""End-to-end analysis pipeline, executed as a background task."""
import json
import logging
from pathlib import Path

import numpy as np
from PIL import Image

from ..core.config import get_settings
from ..core.db import db, now, row_to_dict
from ..forensic.common import dhash, hamming
from ..forensic.image_forensics import analyze_image
from ..forensic.pdf_forensics import analyze_pdf
from ..ml.risk import anomaly_assessment, build_features, score_document
from .audit import audit
from .field_rules import REQUIRED_FIELDS
from .fields import detect_doc_type, extract_fields
from .text_acquisition import acquire_text
from .validation import run_validation

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf

log = logging.getLogger("forensic.pipeline")


def _stage(aid, stage, progress):
    with db() as c:
        c.execute("UPDATE analyses SET stage=?, progress=? WHERE id=?", (stage, progress, aid))


def _first_page_image(path, file_type) -> Image.Image:
    if file_type == "pdf":
        with pymupdf.open(path) as d:
            pix = d[0].get_pixmap(dpi=72, alpha=False)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    im = Image.open(path); im.load()
    return im


def run_analysis(analysis_id: str) -> None:
    s = get_settings()
    try:
        with db() as c:
            a = row_to_dict(c.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone())
            d = row_to_dict(c.execute("SELECT * FROM documents WHERE id=?", (a["document_id"],)).fetchone())
            c.execute("UPDATE analyses SET status='processing' WHERE id=?", (analysis_id,))
            c.execute("UPDATE documents SET status='processing' WHERE id=?", (d["id"],))
        path, ftype, uid = d["stored_path"], d["file_type"], d["user_id"]

        _stage(analysis_id, "extracting_text", 15)
        acq = acquire_text(path, ftype)
        full_text = "\n\n".join(p["text"] for p in acq["pages"]).strip()
        ocr = acq["ocr"]; ocr["warnings"] = acq["warnings"]
        ocr_conf = ocr.get("mean_confidence")

        _stage(analysis_id, "extracting_fields", 40)
        auto, scores = detect_doc_type(full_text)
        doc_type = d["doc_type_selected"] if d["doc_type_selected"] != "auto" else auto
        fields = extract_fields(acq["pages"], doc_type)
        doc_number = next((fields[k]["normalized"] for k in ("document_number", "invoice_number", "account_number") if k in fields), None)

        _stage(analysis_id, "forensic_analysis", 55)
        findings, heat, dims = analyze_image(path) if ftype != "pdf" else analyze_pdf(path)
        img = _first_page_image(path, ftype)
        ph = dhash(img)

        _stage(analysis_id, "duplicate_checks", 70)
        with db() as c:
            same_hash = [dict(r) for r in c.execute(
                "SELECT id, original_filename FROM documents WHERE user_id=? AND sha256=? AND id!=?", (uid, d["sha256"], d["id"]))]
            same_number = [dict(r) for r in c.execute(
                "SELECT d.id, d.original_filename FROM analyses a JOIN documents d ON d.latest_analysis_id=a.id "
                "WHERE a.user_id=? AND a.doc_number=? AND d.id!=? AND d.sha256!=? AND a.status='completed'",
                (uid, doc_number, d["id"], d["sha256"]))] if doc_number else []
            near = []
            for r in c.execute("SELECT id, original_filename, phash FROM documents WHERE user_id=? AND id!=? AND sha256!=? AND phash IS NOT NULL", (uid, d["id"], d["sha256"])):
                dist = hamming(ph, r["phash"])
                if dist <= 6:
                    near.append({"id": r["id"], "original_filename": r["original_filename"], "distance": dist})
            c.execute("UPDATE documents SET phash=? WHERE id=?", (ph, d["id"]))
        dups = {"same_hash": same_hash, "same_number": same_number, "near": near, "number": doc_number, "phash_available": True}

        _stage(analysis_id, "validation", 80)
        validation = run_validation(fields, doc_type, len(full_text), ocr_conf, dups)

        _stage(analysis_id, "risk_scoring", 90)
        req = REQUIRED_FIELDS.get(doc_type, [])
        miss_ratio = round(sum(r not in fields for r in req) / len(req), 3) if req else None
        features = build_features(validation, findings, fields, doc_type, ocr_conf, miss_ratio)
        with db() as c:
            hist = [json.loads(r["features"]) for r in c.execute(
                "SELECT features FROM analyses WHERE user_id=? AND status='completed' AND features IS NOT NULL AND id!=? ORDER BY created_at DESC LIMIT 500", (uid, analysis_id))]
        risk = score_document(validation, findings, len(full_text), ocr_conf, anomaly_assessment(features, hist), features)

        heat_path = None
        if heat:
            hp = s.storage_path / "heatmaps"; hp.mkdir(exist_ok=True)
            heat_path = str(hp / f"{analysis_id}.png")
            Path(heat_path).write_bytes(heat)

        with db() as c:
            c.execute("""UPDATE analyses SET status='completed', stage='done', progress=100, completed_at=?, doc_type=?, doc_number=?,
                         text=?, ocr=?, fields=?, forensic=?, validation=?, features=?, risk=?, category=?, score=?, tech_confidence=?,
                         requires_review=?, heatmap_path=? WHERE id=?""",
                      (now(), doc_type, doc_number, full_text, json.dumps(ocr), json.dumps(fields),
                       json.dumps({"findings": findings, "dimensions": dims}), json.dumps(validation), json.dumps(features),
                       json.dumps({**risk, "detected_type": auto, "type_scores": scores}), risk["category"], risk["score"],
                       risk["technical_confidence"], int(risk["requires_review"]), heat_path, analysis_id))
            c.execute("UPDATE documents SET status='completed', latest_analysis_id=?, page_count=COALESCE(?,page_count) WHERE id=?",
                      (analysis_id, dims.get("page_count"), d["id"]))
            audit(c, uid, "analysis_completed", d["id"], f"category={risk['category']} score={risk['score']}")
    except Exception as e:  # noqa: BLE001
        log.exception("analysis %s failed", analysis_id)
        with db() as c:
            row = c.execute("SELECT document_id, user_id FROM analyses WHERE id=?", (analysis_id,)).fetchone()
            c.execute("UPDATE analyses SET status='failed', stage='failed', error=?, completed_at=? WHERE id=?",
                      (f"Analysis failed: {type(e).__name__}. See server log.", now(), analysis_id))
            if row:
                c.execute("UPDATE documents SET status='failed' WHERE id=?", (row["document_id"],))
                audit(c, row["user_id"], "analysis_failed", row["document_id"], type(e).__name__)
