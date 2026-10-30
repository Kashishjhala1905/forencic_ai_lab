import io
import os
import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image

from ..core.config import get_settings
from ..core.db import db, new_id, now, row_to_dict
from ..forensic.common import png_bytes, sha256_file
from ..services.audit import audit
from ..services.pipeline import run_analysis
from .deps import current_user, owned_document

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf

router = APIRouter(prefix="/api/documents", tags=["documents"])
DOC_TYPES = {"auto", "invoice", "id_card", "certificate", "bank_statement", "general"}
MAGIC = [(b"%PDF-", "pdf"), (b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpeg")]
EXT = {"pdf": ".pdf", "png": ".png", "jpeg": ".jpg"}


def _clean_name(name: str) -> str:
    base = os.path.basename((name or "document").replace("\\", "/"))
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip() or "document"
    return base[:120]


def _sniff(head: bytes) -> str | None:
    if b"%PDF-" in head[:1024]:
        return "pdf"
    return next((t for m, t in MAGIC if head.startswith(m)), None)


def public_doc(d: dict, a: dict | None = None) -> dict:
    out = {k: d[k] for k in ("id", "original_filename", "file_type", "size_bytes", "sha256", "page_count", "width", "height",
                             "doc_type_selected", "status", "latest_analysis_id", "created_at")}
    if a:
        out.update({"analysis_id": a["id"], "analysis_status": a["status"], "stage": a["stage"], "progress": a["progress"], "error": a["error"],
                    "doc_type": a["doc_type"], "category": a["category"], "score": a["score"], "tech_confidence": a["tech_confidence"],
                    "requires_review": bool(a["requires_review"]), "analyzed_at": a["completed_at"]})
    return out


@router.post("/upload", status_code=201)
async def upload(file: UploadFile = File(...), doc_type: str = Form("auto"), user: dict = Depends(current_user)):
    s = get_settings()
    if doc_type not in DOC_TYPES:
        raise HTTPException(422, f"doc_type must be one of {sorted(DOC_TYPES)}.")
    limit = s.max_upload_mb * 1024 * 1024
    udir = s.storage_path / "uploads" / user["id"]
    udir.mkdir(parents=True, exist_ok=True)
    tmp = udir / f"{new_id()}.part"
    size, head = 0, b""
    try:
        with open(tmp, "wb") as out:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File exceeds the {s.max_upload_mb} MB limit.")
                if len(head) < 1024:
                    head += chunk[: 1024 - len(head)]
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, "The uploaded file is empty.")
        ftype = _sniff(head)
        if not ftype:
            raise HTTPException(415, "Unsupported file type. Upload a PDF, PNG or JPEG file.")
        page_count = width = height = None
        try:
            if ftype == "pdf":
                with pymupdf.open(tmp, filetype="pdf") as doc:
                    if doc.needs_pass:
                        raise HTTPException(422, "Password-protected PDFs are not supported.")
                    if doc.page_count < 1:
                        raise HTTPException(422, "The PDF has no pages.")
                    page_count, width, height = doc.page_count, int(doc[0].rect.width), int(doc[0].rect.height)
                    doc[0].get_pixmap(dpi=36)  # forces a real render to catch corrupt content
            else:
                Image.MAX_IMAGE_PIXELS = s.max_image_pixels
                with Image.open(tmp) as im:
                    width, height = im.size
                    if width * height > s.max_image_pixels:
                        raise HTTPException(422, "Image dimensions are too large to process safely.")
                    im.verify()
                with Image.open(tmp) as im:
                    im.load()
                page_count = 1
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001
            raise HTTPException(422, "The file is corrupted or cannot be read as a valid document.")
        did = new_id()
        final = udir / f"{did}{EXT[ftype]}"
        os.replace(tmp, final)
        digest = sha256_file(str(final))
        try:
            with db() as c:
                c.execute("""INSERT INTO documents(id,user_id,original_filename,stored_path,file_type,size_bytes,sha256,page_count,width,height,
                             doc_type_selected,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (did, user["id"], _clean_name(file.filename), str(final), ftype, size, digest, page_count, width, height, doc_type, "uploaded", now()))
                audit(c, user["id"], "document_uploaded", did, _clean_name(file.filename))
                d = row_to_dict(c.execute("SELECT * FROM documents WHERE id=?", (did,)).fetchone())
        except Exception:
            final.unlink(missing_ok=True)
            raise HTTPException(500, "Could not save the document record; the upload was discarded.")
        return public_doc(d)
    finally:
        tmp.unlink(missing_ok=True)


@router.get("")
def list_documents(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), search: str = "", risk: str = "",
                   status: str = "", doc_type: str = "", date_from: str = "", date_to: str = "", user: dict = Depends(current_user)):
    where, args = ["d.user_id=?"], [user["id"]]
    if search:
        where.append("(d.original_filename LIKE ? ESCAPE '\\' OR a.doc_type LIKE ? ESCAPE '\\')")
        like = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        args += [like, like]
    if risk in ("LOW", "MEDIUM", "HIGH", "INSUFFICIENT"):
        where.append("a.category=?"); args.append(risk)
    if status in ("uploaded", "processing", "completed", "failed"):
        where.append("d.status=?"); args.append(status)
    if doc_type:
        where.append("a.doc_type=?"); args.append(doc_type)
    if date_from:
        where.append("d.created_at>=?"); args.append(date_from)
    if date_to:
        where.append("d.created_at<=?"); args.append(date_to + "T23:59:59" if len(date_to) == 10 else date_to)
    w = " AND ".join(where)
    base = "FROM documents d LEFT JOIN analyses a ON a.id=d.latest_analysis_id WHERE " + w
    with db() as c:
        total = c.execute("SELECT COUNT(*) " + base, args).fetchone()[0]
        rows = c.execute("SELECT d.*, a.id AS a_id " + base + " ORDER BY d.created_at DESC LIMIT ? OFFSET ?", args + [page_size, (page - 1) * page_size]).fetchall()
        items = []
        for r in rows:
            d = row_to_dict(r)
            a = row_to_dict(c.execute("SELECT id,status,stage,progress,error,doc_type,category,score,tech_confidence,requires_review,completed_at FROM analyses WHERE id=?", (d["latest_analysis_id"],)).fetchone()) if d["latest_analysis_id"] else None
            items.append(public_doc(d, a))
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.get("/{document_id}")
def get_document(document_id: str, user: dict = Depends(current_user)):
    with db() as c:
        d = owned_document(c, document_id, user)
        latest = row_to_dict(c.execute("SELECT id,status,stage,progress,error,doc_type,category,score,tech_confidence,requires_review,completed_at FROM analyses WHERE id=?", (d["latest_analysis_id"],)).fetchone()) if d["latest_analysis_id"] else None
        if not latest:  # analysis may be queued but not yet linked
            latest = row_to_dict(c.execute("SELECT id,status,stage,progress,error,doc_type,category,score,tech_confidence,requires_review,completed_at FROM analyses WHERE document_id=? ORDER BY created_at DESC LIMIT 1", (d["id"],)).fetchone())
        history = [dict(r) for r in c.execute("SELECT id,status,category,score,created_at,completed_at FROM analyses WHERE document_id=? ORDER BY created_at DESC", (d["id"],))]
    return {**public_doc(d, latest), "analyses": history}


@router.post("/{document_id}/analyze", status_code=202)
def analyze(document_id: str, background: BackgroundTasks, user: dict = Depends(current_user)):
    with db() as c:
        d = owned_document(c, document_id, user)
        busy = c.execute("SELECT id FROM analyses WHERE document_id=? AND status IN ('queued','processing')", (d["id"],)).fetchone()
        if busy:
            raise HTTPException(409, "An analysis is already running for this document.")
        if not Path(d["stored_path"]).exists():
            raise HTTPException(410, "The stored file is missing; please upload it again.")
        aid = new_id()
        c.execute("INSERT INTO analyses(id,document_id,user_id,status,stage,progress,created_at) VALUES (?,?,?,?,?,?,?)",
                  (aid, d["id"], user["id"], "queued", "queued", 0, now()))
        c.execute("UPDATE documents SET status='processing' WHERE id=?", (d["id"],))
        audit(c, user["id"], "analysis_started", d["id"])
    background.add_task(run_analysis, aid)
    return {"analysis_id": aid, "document_id": d["id"], "status": "queued"}


@router.get("/{document_id}/preview")
def preview(document_id: str, user: dict = Depends(current_user)):
    """Safe preview: always a server-rendered PNG of page 1 (the original file is never served inline)."""
    with db() as c:
        d = owned_document(c, document_id, user)
    try:
        if d["file_type"] == "pdf":
            with pymupdf.open(d["stored_path"]) as doc:
                data = doc[0].get_pixmap(dpi=110, alpha=False).tobytes("png")
        else:
            with Image.open(d["stored_path"]) as im:
                im = im.convert("RGB"); im.thumbnail((1400, 1400)); data = png_bytes(im)
    except Exception:  # noqa: BLE001
        raise HTTPException(500, "Preview could not be rendered.")
    return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, user: dict = Depends(current_user)):
    """Deletes the file, heatmaps, generated reports and all DB records for the document. Audit events are kept."""
    with db() as c:
        d = owned_document(c, document_id, user)
        files = [d["stored_path"]]
        for a in c.execute("SELECT id, heatmap_path FROM analyses WHERE document_id=?", (d["id"],)).fetchall():
            if a["heatmap_path"]:
                files.append(a["heatmap_path"])
            for r in c.execute("SELECT path FROM reports WHERE analysis_id=?", (a["id"],)).fetchall():
                files.append(r["path"])
            c.execute("DELETE FROM reports WHERE analysis_id=?", (a["id"],))
        c.execute("DELETE FROM analyses WHERE document_id=?", (d["id"],))
        c.execute("DELETE FROM documents WHERE id=?", (d["id"],))
        audit(c, user["id"], "document_deleted", d["id"], d["original_filename"])
    for f in files:
        try:
            Path(f).unlink(missing_ok=True)
        except OSError:
            pass
    return Response(status_code=204)
