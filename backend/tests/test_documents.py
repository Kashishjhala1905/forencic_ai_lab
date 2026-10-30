import io
from pathlib import Path

from PIL import Image

from app.core.config import get_settings


def test_upload_valid_types(client, user, samples):
    for name, ftype in [("01_normal_invoice.pdf", "pdf"), ("06_normal_id.png", "png"), ("07_clean_invoice.jpg", "jpeg")]:
        r = user.upload(samples / name)
        assert r.status_code == 201, r.text
        j = r.json()
        assert j["file_type"] == ftype and j["status"] == "uploaded" and len(j["sha256"]) == 64 and "stored_path" not in j and j["page_count"] >= 1


def test_rejects_unsupported_and_spoofed(client, user):
    assert user.upload(b"hello world, plain text", "notes.pdf").status_code == 415           # extension lies
    assert user.upload(b"MZ\x90\x00 fake exe", "evil.png").status_code == 415
    assert user.upload(b"", "empty.pdf").status_code == 422


def test_rejects_corrupted(client, user):
    assert user.upload(b"%PDF-1.4\n garbage garbage garbage", "bad.pdf").status_code == 422
    assert user.upload(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, "bad.png").status_code == 422
    assert user.upload(b"\xff\xd8\xff\xe0" + b"\x00" * 50, "bad.jpg").status_code == 422


def test_rejects_oversized(client, user):
    limit = get_settings().max_upload_mb * 1024 * 1024
    r = user.upload(b"%PDF-1.4\n" + b"0" * (limit + 10), "big.pdf")
    assert r.status_code == 413 and "MB" in r.json()["error"]["message"]


def test_filename_is_sanitised_and_storage_name_is_generated(client, user, samples):
    r = user.upload(samples / "01_normal_invoice.pdf", name="../../etc/passwd\x00.pdf")
    assert r.status_code == 201
    assert "/" not in r.json()["original_filename"] and ".." not in r.json()["original_filename"].replace("passwd", "")
    from app.core.db import db
    with db() as c:
        p = c.execute("SELECT stored_path FROM documents WHERE id=?", (r.json()["id"],)).fetchone()[0]
    assert Path(p).parent.parent.name == "uploads" and Path(p).name.startswith(r.json()["id"])


def test_ownership_isolation(client, make_user, samples):
    a, b = make_user(), make_user()
    res = a.analyze(samples / "01_normal_invoice.pdf")
    did, aid = res["_doc_id"], res["id"]
    for method, url in [("get", f"/api/documents/{did}"), ("get", f"/api/documents/{did}/preview"), ("post", f"/api/documents/{did}/analyze"),
                        ("delete", f"/api/documents/{did}"), ("get", f"/api/analysis/{aid}"), ("get", f"/api/analysis/{aid}/report"), ("get", f"/api/analysis/{aid}/heatmap")]:
        assert getattr(client, method)(url, headers=b.h).status_code == 404, url
    assert b.client.get("/api/documents", headers=b.h).json()["total"] == 0
    assert client.get(f"/api/documents/{did}", headers=a.h).status_code == 200


def test_list_pagination_search_filter(client, make_user, samples):
    u = make_user()
    u.analyze(samples / "01_normal_invoice.pdf"); u.analyze(samples / "02_inconsistent_date_id.pdf"); u.analyze(samples / "03_total_mismatch_invoice.pdf")
    g = lambda **p: client.get("/api/documents", headers=u.h, params=p).json()
    assert g()["total"] == 3
    page = g(page=1, page_size=2); assert len(page["items"]) == 2 and page["pages"] == 2
    assert g(search="inconsistent")["total"] == 1
    assert g(search="%")["total"] == 0                       # LIKE wildcard is escaped
    assert g(doc_type="id_card")["total"] == 1
    assert g(risk="HIGH")["total"] >= 1 and all(i["category"] == "HIGH" for i in g(risk="HIGH")["items"])
    assert g(status="completed")["total"] == 3 and g(status="failed")["total"] == 0
    assert g(date_from="2999-01-01")["total"] == 0


def test_delete_removes_files_and_records(client, user, samples):
    a = user.analyze(samples / "08_spliced_invoice.jpg")
    client.get(f"/api/analysis/{a['id']}/report", headers=user.h)
    from app.core.db import db
    with db() as c:
        stored = c.execute("SELECT stored_path FROM documents WHERE id=?", (a["_doc_id"],)).fetchone()[0]
    hm = Path(get_settings().storage_path) / "heatmaps" / f"{a['id']}.png"
    rp = Path(get_settings().storage_path) / "reports" / f"{a['id']}.pdf"
    assert Path(stored).exists() and hm.exists() and rp.exists()
    assert client.delete(f"/api/documents/{a['_doc_id']}", headers=user.h).status_code == 204
    assert not Path(stored).exists() and not hm.exists() and not rp.exists()
    assert client.get(f"/api/documents/{a['_doc_id']}", headers=user.h).status_code == 404
    with db() as c:
        assert c.execute("SELECT COUNT(*) FROM analyses WHERE document_id=?", (a["_doc_id"],)).fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM audit_events WHERE document_id=? AND action='document_deleted'", (a["_doc_id"],)).fetchone()[0] == 1


def test_reanalysis_creates_new_analysis(client, user, samples):
    a = user.analyze(samples / "01_normal_invoice.pdf")
    r = client.post(f"/api/documents/{a['_doc_id']}/analyze", headers=user.h); assert r.status_code == 202
    d = client.get(f"/api/documents/{a['_doc_id']}", headers=user.h).json()
    assert len(d["analyses"]) == 2 and d["latest_analysis_id"] == r.json()["analysis_id"]


def test_preview_is_rendered_png(client, user, samples):
    did = user.upload(samples / "01_normal_invoice.pdf").json()["id"]
    r = client.get(f"/api/documents/{did}/preview", headers=user.h)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and Image.open(io.BytesIO(r.content)).size[0] > 100


def test_unknown_ids_404_not_500(client, user):
    assert client.get("/api/documents/' OR 1=1 --", headers=user.h).status_code == 404
    assert client.get("/api/analysis/does-not-exist", headers=user.h).status_code == 404
