"""Rule-based field extraction with provenance (method, confidence, page, validation status)."""
import re
from decimal import Decimal

from ..utils.text import parse_amount, parse_date
from .field_rules import FIELD_RULES, TYPE_KEYWORDS


def detect_doc_type(text: str) -> tuple[str, dict]:
    low = text.lower()
    scores = {t: sum(1 for k in kws if k in low) for t, kws in TYPE_KEYWORDS.items()}
    best = max(scores, key=scores.get) if scores else "general"
    return (best if scores.get(best, 0) >= 2 else "general"), scores


def _confidence(page: dict, value: str) -> float | None:
    if page["source"] != "ocr" or not page["words"]:
        return None
    toks = {t.lower() for t in re.findall(r"\w+", value)}
    confs = [c for w, c in page["words"] if w.lower().strip(".,:;") in toks or any(t in w.lower() for t in toks if len(t) > 3)]
    return round(sum(confs) / len(confs), 1) if confs else page["mean_conf"]


def _norm(kind: str, raw: str) -> str:
    if kind == "amount":
        a = parse_amount(raw)
        return str(a) if a is not None else raw
    if kind == "date":
        d, _ = parse_date(raw)
        return d.isoformat() if d else raw
    return re.sub(r"\s+", " ", raw).strip().upper() if kind == "id" else raw.strip()


def extract_fields(pages: list[dict], doc_type: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, rule in FIELD_RULES.items():
        if doc_type not in rule["types"]:
            continue
        hits = []
        for tier in rule["patterns"]:
            for p in pages:
                for m in re.finditer(tier, p["text"]):
                    raw = (m.group(m.lastindex or 0) or "").strip(" :-\t")
                    if raw:
                        hits.append((raw, p, m.group(0).strip().lower()))
            if hits:
                break
        if not hits:
            continue
        kind = rule["kind"]
        distinct: list[str] = []
        for raw, _, _l in hits:
            n = _norm(kind, raw)
            if n not in distinct:
                distinct.append(n)
        method_suffix = ""
        raw, page, _ = hits[0]
        value = raw
        lines = {h[2]: h for h in hits}          # unique matched lines (CGST 90 + SGST 90 are two lines, one value)
        if rule.get("sum_multiple") and len(lines) > 1:
            total = sum((parse_amount(h[0]) or Decimal(0)) for h in lines.values())
            value, method_suffix, distinct = str(total), "+sum_of_tax_lines", [str(total)]
        field = {
            "name": name, "label": rule["label"], "kind": kind, "value": value,
            "normalized": _norm(kind, value), "page": page["page"],
            "method": f"{page['source']}+regex{method_suffix}",
            "confidence": _confidence(page, raw), "validation_status": "unchecked", "validation_note": None,
            "candidates": distinct, "conflict": bool(rule["single"] and len(distinct) > 1),
        }
        if kind == "date":
            d, amb = parse_date(raw)
            field["validation_status"] = "valid" if d else "invalid"
            field["validation_note"] = ("Ambiguous day/month order; day-first assumed." if amb else None) if d else "Not a valid calendar date."
        elif kind == "amount":
            ok = parse_amount(value) is not None
            field["validation_status"] = "valid" if ok else "invalid"
            field["validation_note"] = None if ok else "Could not parse as a number."
        out[name] = field
    return out
