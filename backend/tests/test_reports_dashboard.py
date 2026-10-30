import pytest

from tests.conftest import rule


def test_report_download_is_pdf_and_audited(client, user, samples):
    a = user.analyze(samples / "03_total_mismatch_invoice.pdf")
    r = client.get(f"/api/analysis/{a['id']}/report", headers=user.h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF") and len(r.content) > 2000
    assert "attachment" in r.headers["content-disposition"]
    acts = [e["action"] for e in client.get("/api/dashboard/recent", headers=user.h).json()["recent_activity"]]
    assert "report_downloaded" in acts and "analysis_completed" in acts


def test_report_not_available_before_completion(client, user, samples):
    from app.core.db import db, new_id, now
    did = user.upload(samples / "01_normal_invoice.pdf").json()["id"]; aid = new_id()
    with db() as c:
        c.execute("INSERT INTO analyses(id,document_id,user_id,status,created_at) VALUES (?,?,?,?,?)", (aid, did, user.id, "processing", now()))
    assert client.get(f"/api/analysis/{aid}/report", headers=user.h).status_code == 409


def test_report_escapes_hostile_text(client, user, tmp_path):
    from app.utils.synthetic import render_pdf
    p = tmp_path / "hostile.pdf"
    render_pdf(["INVOICE", "Invoice No: A-1", "Bill To: <b>Eve</b> <font color=red>&amp;</font> <img src=x>", "Total Amount: 5.00"], p)
    a = user.analyze(p)
    assert client.get(f"/api/analysis/{a['id']}/report", headers=user.h).status_code == 200


def test_dashboard_reflects_persisted_data(client, make_user, samples):
    u = make_user()
    empty = client.get("/api/dashboard/stats", headers=u.h).json()
    assert empty["total_documents"] == 0 and empty["manual_review"] == 0 and sum(empty["risk_distribution"].values()) == 0
    u.analyze(samples / "01_normal_invoice.pdf"); u.analyze(samples / "03_total_mismatch_invoice.pdf"); u.upload(samples / "06_normal_id.png")
    s = client.get("/api/dashboard/stats", headers=u.h).json()
    assert s["total_documents"] == 3 and s["analyzed"] == 2 and s["low_risk"] == 1 and s["medium_risk"] + s["high_risk"] == 1
    assert s["by_status"] == {"completed": 2, "uploaded": 1} and s["manual_review"] == 1 and sum(d["count"] for d in s["daily"]) == 2
    rec = client.get("/api/dashboard/recent", headers=u.h).json()
    assert len(rec["recent_analyses"]) == 2 and rec["recent_activity"][0]["action"] in ("analysis_completed", "document_uploaded")


def test_audit_never_contains_secrets(client, make_user, samples):
    from app.core.db import db
    u = make_user(); u.analyze(samples / "01_normal_invoice.pdf")
    with db() as c:
        rows = " ".join(str(tuple(r)) for r in c.execute("SELECT * FROM audit_events"))
    assert u.password not in rows and u.token not in rows and "INV-2024-0042" not in rows


def test_failed_analysis_is_reported_honestly(client, user, samples):
    from app.core.db import db
    did = user.upload(samples / "01_normal_invoice.pdf").json()["id"]
    with db() as c:
        p = c.execute("SELECT stored_path FROM documents WHERE id=?", (did,)).fetchone()[0]
    import os; os.rename(p, p + ".moved")
    r = client.post(f"/api/documents/{did}/analyze", headers=user.h)
    assert r.status_code == 410
    os.rename(p + ".moved", p)


def test_concurrent_analysis_rejected(client, user, samples):
    from app.core.db import db, new_id, now
    did = user.upload(samples / "01_normal_invoice.pdf").json()["id"]
    with db() as c:
        c.execute("INSERT INTO analyses(id,document_id,user_id,status,created_at) VALUES (?,?,?,?,?)", (new_id(), did, user.id, "processing", now()))
    assert client.post(f"/api/documents/{did}/analyze", headers=user.h).status_code == 409
