"""Cross-field and logical validation. A rule is never 'fail' when the data needed could not be extracted."""
from datetime import date

from ..utils.text import parse_amount, parse_date, today
from .field_rules import REQUIRED_FIELDS


def _r(rule, label, status, severity, explanation, evidence=None):
    return {"rule": rule, "label": label, "status": status, "severity": severity if status == "fail" else "info",
            "explanation": explanation, "evidence": evidence or {}}


def _d(fields, name) -> date | None:
    f = fields.get(name)
    return parse_date(f["value"])[0] if f else None


def run_validation(fields: dict, doc_type: str, text_len: int, ocr_conf: float | None, dups: dict) -> list[dict]:
    res = []
    text_ok = text_len >= 30 and (ocr_conf is None or ocr_conf >= 40)

    # 1. mandatory fields
    req = REQUIRED_FIELDS.get(doc_type, [])
    if not req:
        res.append(_r("required_fields", "Mandatory fields present", "not_applicable", "info", "No mandatory fields are defined for this document type."))
    elif not text_ok:
        res.append(_r("required_fields", "Mandatory fields present", "not_applicable", "info",
                      "Too little reliable text was extracted to judge which fields are genuinely missing.", {"text_chars": text_len, "ocr_confidence": ocr_conf}))
    else:
        missing = [n for n in req if n not in fields]
        res.append(_r("required_fields", "Mandatory fields present", "fail" if missing else "pass",
                      "medium" if len(missing) >= 2 else "low",
                      f"Missing for {doc_type}: {', '.join(missing)}." if missing else "All mandatory fields were found.",
                      {"required": req, "missing": missing}))

    # 2. date formats
    dfs = [f for f in fields.values() if f["kind"] == "date"]
    bad = [{"field": f["name"], "value": f["value"]} for f in dfs if f["validation_status"] == "invalid"]
    res.append(_r("date_formats_valid", "Dates are valid calendar dates", "not_applicable" if not dfs else "fail" if bad else "pass", "medium",
                  "No date fields extracted." if not dfs else "Unparseable or impossible dates found." if bad else "All extracted dates parse as valid dates.",
                  {"invalid": bad} if bad else {"checked": [f["name"] for f in dfs]}))

    issue, expiry, dob, due = (_d(fields, n) for n in ("issue_date", "expiry_date", "date_of_birth", "due_date"))
    # 3. expiry after issue
    if issue and expiry:
        res.append(_r("expiry_after_issue", "Expiry date is after issue date", "fail" if expiry <= issue else "pass", "high",
                      "Expiry date is on or before the issue date." if expiry <= issue else "Expiry date follows issue date.",
                      {"issue_date": issue.isoformat(), "expiry_date": expiry.isoformat()}))
    else:
        res.append(_r("expiry_after_issue", "Expiry date is after issue date", "not_applicable", "info", "Both issue and expiry dates are required and were not both extracted."))
    # 4. dob before issue, plausible
    if dob:
        age = (today() - dob).days / 365.25
        probs = []
        if dob > today(): probs.append("date of birth is in the future")
        if age > 120: probs.append("implied age exceeds 120 years")
        if issue and dob >= issue: probs.append("date of birth is not before issue date")
        res.append(_r("dob_before_issue", "Date of birth is plausible and precedes issue", "fail" if probs else "pass", "high",
                      "; ".join(probs).capitalize() + "." if probs else "Date of birth is plausible.", {"date_of_birth": dob.isoformat(), "issue_date": issue and issue.isoformat()}))
    else:
        res.append(_r("dob_before_issue", "Date of birth is plausible and precedes issue", "not_applicable", "info", "No date of birth extracted."))
    # 5. issue not in future
    if issue:
        res.append(_r("issue_not_future", "Issue date is not in the future", "fail" if issue > today() else "pass", "medium",
                      "Issue date is later than today." if issue > today() else "Issue date is not in the future.", {"issue_date": issue.isoformat()}))
    else:
        res.append(_r("issue_not_future", "Issue date is not in the future", "not_applicable", "info", "No issue date extracted."))
    # 6. invoice due date
    if issue and due:
        res.append(_r("due_after_invoice", "Due date is not before invoice date", "fail" if due < issue else "pass", "low",
                      "Payment due date precedes the invoice date." if due < issue else "Due date is on/after invoice date.",
                      {"invoice_date": issue.isoformat(), "due_date": due.isoformat()}))
    else:
        res.append(_r("due_after_invoice", "Due date is not before invoice date", "not_applicable", "info", "Invoice date and due date are both required."))
    # 7. expired (informational, not scored)
    if expiry:
        exp = expiry < today()
        res.append(_r("document_not_expired", "Document is within validity period", "fail" if exp else "pass", "info",
                      "Document has expired (informational; expiry alone is not an indicator of fraud)." if exp else "Document is within its validity period.",
                      {"expiry_date": expiry.isoformat()}))
        if exp: res[-1]["severity"] = "info"
    # 8. invoice arithmetic
    sub, tax, tot = (parse_amount(fields[n]["value"]) if n in fields else None for n in ("subtotal", "tax_amount", "total_amount"))
    if doc_type == "invoice" and sub is not None and tax is not None and tot is not None:
        diff = abs(sub + tax - tot)
        tol = max(0.02, 0.0)
        res.append(_r("invoice_total_consistency", "Subtotal + tax = total", "fail" if diff > tol else "pass", "high",
                      f"Subtotal {sub} + tax {tax} = {sub + tax}, but the stated total is {tot} (difference {diff})." if diff > tol else "Subtotal plus tax equals the stated total.",
                      {"subtotal": str(sub), "tax": str(tax), "total": str(tot), "difference": str(diff)}))
    else:
        res.append(_r("invoice_total_consistency", "Subtotal + tax = total", "not_applicable", "info",
                      "Requires an invoice with subtotal, tax and total all extracted."))
    # 9. conflicting values
    conflicts = {n: f["candidates"] for n, f in fields.items() if f["conflict"]}
    res.append(_r("conflicting_values", "No conflicting values for the same field", "fail" if conflicts else "pass", "medium",
                  "Different values were found for: " + ", ".join(conflicts) + "." if conflicts else "No field has competing values.", {"conflicts": conflicts}))
    # 10. duplicates
    if dups.get("same_number"):
        res.append(_r("duplicate_document_number", "Document number is unique", "fail", "high",
                      "The same document number appears in another of your documents with different content.", {"other_documents": dups["same_number"]}))
    else:
        res.append(_r("duplicate_document_number", "Document number is unique", "pass" if dups.get("number") else "not_applicable", "high",
                      "No other document of yours uses this number." if dups.get("number") else "No document/invoice/account number extracted."))
    res.append(_r("duplicate_file", "File has not been uploaded before", "fail" if dups.get("same_hash") else "pass", "low",
                  "Byte-identical file already exists in your history." if dups.get("same_hash") else "No identical file in your history.",
                  {"other_documents": dups.get("same_hash", [])}))
    res.append(_r("visually_similar_document", "No near-identical page image", "fail" if dups.get("near") else "pass" if dups.get("phash_available") else "not_applicable", "low",
                  "A visually near-identical but not byte-identical document exists (may be a re-scan, edited copy or the same template)." if dups.get("near")
                  else "No visually near-identical document found." if dups.get("phash_available") else "Perceptual hash unavailable.",
                  {"other_documents": dups.get("near", [])}))
    return res
