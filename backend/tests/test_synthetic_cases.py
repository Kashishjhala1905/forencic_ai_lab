"""Behavioural tests on SYNTHETIC documents. They verify the software does what it is specified to do;
they say nothing about accuracy on real-world fraud."""
import pytest

from tests.conftest import needs_ocr, rule


def test_normal_invoice_is_low_risk(user, samples):
    a = user.analyze(samples / "01_normal_invoice.pdf")
    assert a["doc_type"] == "invoice" and a["category"] == "LOW" and a["score"] == 0
    f = {x["name"]: x for x in a["fields"]}
    assert f["invoice_number"]["value"] == "INV-2024-0042" and f["total_amount"]["normalized"] == "1180.00" and f["invoice_number"]["method"] == "pdf_text+regex"
    assert rule(a, "invoice_total_consistency")["status"] == "pass" and rule(a, "required_fields")["status"] == "pass"
    assert a["risk"]["technical_confidence"] > 60


def test_inconsistent_date_is_flagged(user, samples):
    a = user.analyze(samples / "02_inconsistent_date_id.pdf")
    r = rule(a, "expiry_after_issue")
    assert a["doc_type"] == "id_card" and r["status"] == "fail" and r["severity"] == "high"
    assert r["evidence"] == {"issue_date": "2022-01-10", "expiry_date": "2020-01-09"}
    assert any(c["key"] == "expiry_after_issue" for c in a["risk"]["contributions"]) and a["category"] in ("MEDIUM", "HIGH")


def test_total_mismatch_is_flagged(user, samples):
    a = user.analyze(samples / "03_total_mismatch_invoice.pdf")
    r = rule(a, "invoice_total_consistency")
    assert r["status"] == "fail" and r["evidence"]["difference"] == "200.00" and a["category"] in ("MEDIUM", "HIGH")
    assert a["score"] >= 35


def test_missing_required_field_is_reported_not_invented(user, samples):
    a = user.analyze(samples / "04_missing_field_invoice.pdf")
    r = rule(a, "required_fields")
    assert r["status"] == "fail" and r["evidence"]["missing"] == ["invoice_number"]
    assert "invoice_number" not in {f["name"] for f in a["fields"]}


def test_duplicate_identifier_flagged_on_second_document_only(user, samples):
    first = user.analyze(samples / "01_normal_invoice.pdf")
    assert rule(first, "duplicate_document_number")["status"] == "pass"
    second = user.analyze(samples / "05_duplicate_identifier_invoice.pdf")
    r = rule(second, "duplicate_document_number")
    assert r["status"] == "fail" and r["evidence"]["other_documents"][0]["id"] == first["_doc_id"]
    assert second["category"] in ("MEDIUM", "HIGH")


def test_duplicate_is_scoped_to_the_same_user(make_user, samples):
    a, b = make_user(), make_user()
    a.analyze(samples / "01_normal_invoice.pdf")
    assert rule(b.analyze(samples / "05_duplicate_identifier_invoice.pdf"), "duplicate_document_number")["status"] == "pass"


def test_identical_file_reupload_detected(user, samples):
    user.analyze(samples / "01_normal_invoice.pdf")
    again = user.analyze(samples / "01_normal_invoice.pdf")
    assert rule(again, "duplicate_file")["status"] == "fail"


def test_pdf_with_editor_producer_flagged(user, samples):
    a = user.analyze(samples / "09_edited_producer_invoice.pdf")
    f = {x["key"]: x for x in a["forensic"]["findings"]}
    assert f["pdf_metadata"]["flagged"] and f["pdf_metadata"]["severity"] == "medium" and "Photoshop" in f["pdf_metadata"]["summary"]


def test_ela_not_applicable_to_pdf_and_png_and_no_fake_heatmap(client, user, samples):
    for name in ("01_normal_invoice.pdf", "06_normal_id.png"):
        if name.endswith("png") and not __import__("tests.conftest", fromlist=["OCR"]).OCR:
            continue
        a = user.analyze(samples / name)
        ela = next(x for x in a["forensic"]["findings"] if x["key"] == "ela")
        assert ela["status"] == "not_applicable" and not a["has_heatmap"]
        assert client.get(f"/api/analysis/{a['id']}/heatmap", headers=user.h).status_code == 404


@needs_ocr
def test_ocr_path_on_png(user, samples):
    a = user.analyze(samples / "02_inconsistent_date_id.png")
    assert a["ocr"]["used"] and a["ocr"]["mean_confidence"] > 60
    assert {f["name"] for f in a["fields"]} >= {"person_or_org_name", "document_number", "issue_date", "expiry_date"}
    assert all(f["method"] == "ocr+regex" and f["confidence"] is not None for f in a["fields"])
    assert rule(a, "expiry_after_issue")["status"] == "fail"


@needs_ocr
def test_ela_flags_splice_but_not_clean_scan(client, user, samples):
    clean = user.analyze(samples / "07_clean_invoice.jpg")
    spliced = user.analyze(samples / "08_spliced_invoice.jpg")
    ela = lambda a: next(x for x in a["forensic"]["findings"] if x["key"] == "ela")
    assert ela(clean)["status"] == "completed" and not ela(clean)["flagged"]
    assert ela(spliced)["flagged"] and ela(spliced)["details"]["regions"] and spliced["has_heatmap"]
    r = client.get(f"/api/analysis/{spliced['id']}/heatmap", headers=user.h)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert ela(spliced)["limitation"]


def test_blank_image_is_insufficient_evidence_not_low_risk(user, tmp_path):
    from PIL import Image
    p = tmp_path / "blank.png"; Image.new("RGB", (800, 600), "white").save(p)
    a = user.analyze(p)
    assert a["category"] == "INSUFFICIENT" and a["risk"]["label"].startswith("INSUFFICIENT") and a["requires_review"]
    assert all(v["status"] != "fail" for v in a["validation"] if v["rule"] == "required_fields")
    assert a["fields"] == []
