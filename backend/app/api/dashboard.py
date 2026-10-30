from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from ..core.db import db
from .deps import admin_user, current_user

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/stats")
def stats(user: dict = Depends(current_user)):
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM documents WHERE user_id=?", (user["id"],)).fetchone()[0]
        by_status = {r[0]: r[1] for r in c.execute("SELECT status, COUNT(*) FROM documents WHERE user_id=? GROUP BY status", (user["id"],))}
        cats = {r[0]: r[1] for r in c.execute(
            "SELECT a.category, COUNT(*) FROM documents d JOIN analyses a ON a.id=d.latest_analysis_id WHERE d.user_id=? AND a.status='completed' GROUP BY a.category", (user["id"],))}
        review = c.execute("SELECT COUNT(*) FROM documents d JOIN analyses a ON a.id=d.latest_analysis_id WHERE d.user_id=? AND a.requires_review=1", (user["id"],)).fetchone()[0]
        since = (datetime.now(timezone.utc) - timedelta(days=13)).date().isoformat()
        daily = {r[0]: r[1] for r in c.execute(
            "SELECT substr(completed_at,1,10), COUNT(*) FROM analyses WHERE user_id=? AND status='completed' AND completed_at>=? GROUP BY 1", (user["id"], since))}
    days = [(datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat() for i in range(13, -1, -1)]
    analyzed = sum(cats.values())
    return {"total_documents": total, "analyzed": analyzed, "by_status": by_status,
            "risk_distribution": {k: cats.get(k, 0) for k in ("LOW", "MEDIUM", "HIGH", "INSUFFICIENT")},
            "low_risk": cats.get("LOW", 0), "medium_risk": cats.get("MEDIUM", 0), "high_risk": cats.get("HIGH", 0),
            "insufficient": cats.get("INSUFFICIENT", 0), "manual_review": review,
            "daily": [{"date": d, "count": daily.get(d, 0)} for d in days]}


@router.get("/api/dashboard/recent")
def recent(user: dict = Depends(current_user)):
    with db() as c:
        analyses = [dict(r) for r in c.execute(
            "SELECT d.id AS document_id, d.original_filename, a.id AS analysis_id, a.category, a.score, a.doc_type, a.completed_at "
            "FROM documents d JOIN analyses a ON a.id=d.latest_analysis_id WHERE d.user_id=? AND a.status='completed' ORDER BY a.completed_at DESC LIMIT 6", (user["id"],))]
        activity = [dict(r) for r in c.execute(
            "SELECT action, document_id, detail, created_at FROM audit_events WHERE user_id=? ORDER BY id DESC LIMIT 10", (user["id"],))]
    return {"recent_analyses": analyses, "recent_activity": activity}


@router.get("/api/admin/overview")
def admin_overview(_: dict = Depends(admin_user)):
    from .health import health_payload
    with db() as c:
        counts = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users", "documents", "analyses", "reports", "audit_events")}
        failed = c.execute("SELECT COUNT(*) FROM analyses WHERE status='failed'").fetchone()[0]
        events = [dict(r) for r in c.execute(
            "SELECT e.action, e.created_at, e.document_id, u.email FROM audit_events e LEFT JOIN users u ON u.id=e.user_id ORDER BY e.id DESC LIMIT 25")]
    return {"counts": counts, "failed_analyses": failed, "health": health_payload(), "recent_events": events}
