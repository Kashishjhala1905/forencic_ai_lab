from fastapi import APIRouter

from ..core.db import db
from ..services.text_acquisition import ocr_status

router = APIRouter(tags=["health"])


def health_payload() -> dict:
    try:
        with db() as c:
            c.execute("SELECT 1").fetchone()
        database = {"ok": True, "engine": "sqlite"}
    except Exception as e:  # noqa: BLE001
        database = {"ok": False, "error": type(e).__name__}
    ocr = ocr_status()
    return {"status": "ok" if database["ok"] else "error", "database": database, "ocr": ocr,
            "degraded": [] if ocr["available"] else ["OCR unavailable: scanned documents/images cannot be read"]}


@router.get("/api/health")
def health():
    return health_payload()
