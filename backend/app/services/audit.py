def audit(conn, user_id, action, document_id=None, detail=None):
    """Record an audit event. `detail` must never contain passwords, tokens or document text."""
    from ..core.db import now
    conn.execute("INSERT INTO audit_events(user_id, action, document_id, detail, created_at) VALUES (?,?,?,?,?)",
                 (user_id, action, document_id, (detail or "")[:300] or None, now()))
