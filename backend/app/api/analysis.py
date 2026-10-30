from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..core.db import db, new_id, now
from ..services.audit import audit
from ..services.report import build_report
from .deps import current_user, owned_analysis, owned_document

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _public(a: dict, d: dict) -> dict:
    return {"id": a["id"], "document_id": a["document_id"], "status": a["status"], "stage": a["stage"], "progress": a["progress"], "error": a["error"],
            "created_at": a["created_at"], "completed_at": a["completed_at"], "doc_type": a["doc_type"], "text": a["text"], "ocr": a["ocr"],
            "fields": list((a["fields"] or {}).values()), "forensic": a["forensic"], "validation": a["validation"], "risk": a["risk"],
            "category": a["category"], "score": a["score"], "tech_confidence": a["tech_confidence"], "requires_review": bool(a["requires_review"]),
            "has_heatmap": bool(a["heatmap_path"]), "document": {k: d[k] for k in ("id", "original_filename", "file_type", "size_bytes", "page_count", "width", "height", "created_at")}}


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, user: dict = Depends(current_user)):
    with db() as c:
        a = owned_analysis(c, analysis_id, user)
        d = owned_document(c, a["document_id"], user)
    return _public(a, d)


@router.get("/{analysis_id}/heatmap")
def heatmap(analysis_id: str, user: dict = Depends(current_user)):
    with db() as c:
        a = owned_analysis(c, analysis_id, user)
    if not a["heatmap_path"] or not Path(a["heatmap_path"]).exists():
        raise HTTPException(404, "No ELA heatmap exists for this analysis (ELA did not run).")
    return FileResponse(a["heatmap_path"], media_type="image/png")


@router.get("/{analysis_id}/report")
def report(analysis_id: str, user: dict = Depends(current_user)):
    with db() as c:
        a = owned_analysis(c, analysis_id, user)
        d = owned_document(c, a["document_id"], user)
    if a["status"] != "completed":
        raise HTTPException(409, "The analysis has not completed; no report is available.")
    try:
        path = build_report(a, d, user)
    except Exception:  # noqa: BLE001
        raise HTTPException(500, "Report generation failed.")
    with db() as c:
        c.execute("INSERT INTO reports(id,analysis_id,user_id,path,created_at) VALUES (?,?,?,?,?)", (new_id(), a["id"], user["id"], str(path), now()))
        audit(c, user["id"], "report_downloaded", d["id"])
    stem = Path(d["original_filename"]).stem[:40].replace(" ", "_") or "document"
    return FileResponse(path, media_type="application/pdf", filename=f"forensic-report-{''.join(ch for ch in stem if ch.isalnum() or ch in '_-')}.pdf")
