"""Transparent, configurable risk scoring + optional unsupervised anomaly context.

Scores are NOT probabilities of fraud. Technical confidence (how much evidence the system could evaluate) is
reported separately from risk. No supervised model is trained: no verified labelled data exists.
"""
import json
import math
from copy import deepcopy
from functools import lru_cache

import numpy as np

from ..core.config import get_settings

DEFAULT_CONFIG = {
    # Points added when an indicator fires. A number, or a {severity: points} map.
    "points": {
        "expiry_after_issue": 35, "dob_before_issue": 35, "invoice_total_consistency": 35,
        "duplicate_document_number": 25, "conflicting_values": 20, "issue_not_future": 15,
        "date_formats_valid": 10, "required_fields": {"low": 8, "medium": 14}, "due_after_invoice": 8,
        "duplicate_file": 4, "visually_similar_document": 3,
        "image_metadata": {"low": 6, "medium": 20}, "pdf_metadata": {"low": 6, "medium": 20},
        "pdf_revisions": {"low": 5, "medium": 12}, "pdf_active_content": 15, "pdf_annotations": 5,
        "pdf_fonts": 6, "ela": {"low": 8, "medium": 18},
    },
    "thresholds": {"medium": 20, "high": 50},          # score < medium => LOW; < high => MEDIUM; else HIGH
    "insufficient": {"min_technical_confidence": 35, "min_text_chars": 30},
    "anomaly": {"enabled": True, "min_history": 30, "weight": 0.0},  # weight 0 => shown for context, not scored
}
LABELS = {"LOW": "LOW RISK", "MEDIUM": "MEDIUM RISK", "HIGH": "HIGH RISK", "INSUFFICIENT": "INSUFFICIENT EVIDENCE / MANUAL REVIEW"}
FEATURES = ["failed_validation_count", "flagged_forensic_count", "missing_required_ratio", "ocr_confidence",
            "fields_extracted", "date_issue", "amount_mismatch", "duplicate_indicator", "metadata_anomaly", "ela_flagged_ratio"]


@lru_cache
def get_config() -> dict:
    cfg = deepcopy(DEFAULT_CONFIG)
    p = get_settings().risk_config_path
    if p:
        with open(p, encoding="utf-8") as f:
            user = json.load(f)
        for k, v in user.items():
            cfg[k] = {**cfg.get(k, {}), **v} if isinstance(v, dict) else v
    return cfg


def _pts(cfg, key, severity):
    p = cfg["points"].get(key)
    if isinstance(p, dict):
        return p.get(severity, max(p.values()) if severity == "high" else 0)
    return p or 0


def build_features(validation, forensic, fields, doc_type, ocr_conf, required_missing_ratio) -> dict:
    fv = {r["rule"]: r for r in validation}
    failed = [r for r in validation if r["status"] == "fail" and r["severity"] != "info"]
    flagged = [f for f in forensic if f["flagged"]]
    ela = next((f for f in forensic if f["key"] == "ela" and f["status"] == "completed"), None)
    return {
        "failed_validation_count": len(failed), "flagged_forensic_count": len(flagged),
        "missing_required_ratio": required_missing_ratio, "ocr_confidence": ocr_conf,
        "fields_extracted": len(fields),
        "date_issue": int(any(fv.get(k, {}).get("status") == "fail" for k in ("expiry_after_issue", "dob_before_issue", "issue_not_future", "date_formats_valid"))),
        "amount_mismatch": int(fv.get("invoice_total_consistency", {}).get("status") == "fail"),
        "duplicate_indicator": int(any(fv.get(k, {}).get("status") == "fail" for k in ("duplicate_document_number", "duplicate_file", "visually_similar_document"))),
        "metadata_anomaly": int(any(f["key"] in ("image_metadata", "pdf_metadata") and f["flagged"] for f in forensic)),
        "ela_flagged_ratio": ela["details"].get("flagged_ratio") if ela else None,
    }


def technical_confidence(text_chars, ocr_conf, forensic, validation) -> tuple[float, dict]:
    text = min(1.0, text_chars / 200) * (min(ocr_conf, 100) / 100 if ocr_conf is not None else 1.0)
    fx = [f for f in forensic if f["status"] != "not_applicable"]
    fcov = sum(f["status"] == "completed" for f in fx) / len(fx) if fx else 0.0
    ev = sum(r["status"] in ("pass", "fail") for r in validation) / max(len(validation), 1)
    parts = {"text_quality": round(text * 100), "forensic_coverage": round(fcov * 100), "validation_coverage": round(ev * 100)}
    return round(40 * text + 30 * fcov + 30 * ev, 1), parts


def anomaly_assessment(features: dict, history: list[dict]) -> dict:
    cfg = get_config()["anomaly"]
    if not cfg["enabled"]:
        return {"available": False, "reason": "Disabled in configuration."}
    if len(history) < cfg["min_history"]:
        return {"available": False, "reason": f"Needs at least {cfg['min_history']} previously analysed documents for a meaningful baseline (have {len(history)}). No model is fitted on invented labels."}
    from sklearn.ensemble import IsolationForest
    X = np.array([[h.get(k) if h.get(k) is not None else np.nan for k in FEATURES] for h in history], dtype=float)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-missing column -> median 0
        med = np.nan_to_num(np.nanmedian(X, axis=0), nan=0.0)
    X = np.where(np.isnan(X), med, X)
    x = np.array([[features.get(k) if features.get(k) is not None else med[i] for i, k in enumerate(FEATURES)]], dtype=float)
    model = IsolationForest(n_estimators=200, random_state=0).fit(X)
    base = model.score_samples(X)
    s = float(model.score_samples(x)[0])
    pct = float((base <= s).mean() * 100)   # share of history at least as anomalous as this document
    return {"available": True, "baseline_size": len(history), "raw_score": round(s, 4),
            "atypicality_percentile": round(100 - pct, 1),
            "note": "Higher percentile = more unusual compared with YOUR previous documents. Not a fraud probability."}


def score_document(validation, forensic, text_chars, ocr_conf, anomaly, features) -> dict:
    cfg = get_config()
    contribs = []
    for r in validation:
        if r["status"] == "fail" and r["severity"] != "info":
            p = _pts(cfg, r["rule"], r["severity"])
            if r["rule"] == "required_fields":
                p += 3 * max(0, len(r["evidence"].get("missing", [])) - 1)
            if p:
                contribs.append({"key": r["rule"], "label": r["label"], "source": "validation", "severity": r["severity"], "points": p, "explanation": r["explanation"]})
    for f in forensic:
        if f["flagged"] and f["status"] == "completed":
            p = _pts(cfg, f["key"], f["severity"])
            if p:
                contribs.append({"key": f["key"], "label": f["name"], "source": "forensic", "severity": f["severity"], "points": p, "explanation": f["summary"]})
    if anomaly.get("available") and cfg["anomaly"]["weight"] > 0:
        p = round(cfg["anomaly"]["weight"] * anomaly["atypicality_percentile"] / 100 * 100, 1)
        contribs.append({"key": "anomaly_model", "label": "Atypical vs. your history", "source": "ml", "severity": "low", "points": p, "explanation": anomaly["note"]})
    contribs.sort(key=lambda c: -c["points"])
    score = min(100.0, float(sum(c["points"] for c in contribs)))
    conf, parts = technical_confidence(text_chars, ocr_conf, forensic, validation)
    th, ins = cfg["thresholds"], cfg["insufficient"]
    insufficient = conf < ins["min_technical_confidence"] or text_chars < ins["min_text_chars"]
    if score >= th["high"]:
        cat = "HIGH"
    elif insufficient:
        cat = "INSUFFICIENT"
    elif score >= th["medium"]:
        cat = "MEDIUM"
    else:
        cat = "LOW"
    reasons = []
    if insufficient:
        reasons.append(f"Technical confidence {conf}/100 or extracted text ({text_chars} chars) is below the minimum needed for a reliable assessment.")
    return {"score": round(score, 1), "category": cat, "label": LABELS[cat], "technical_confidence": conf, "confidence_breakdown": parts,
            "contributions": contribs, "insufficient_reasons": reasons, "requires_review": cat != "LOW",
            "thresholds": th, "anomaly": anomaly, "features": features,
            "disclaimer": "The score is a rule-weighted indicator sum, not a probability of fraud. Automated analysis supports human review and does not establish fraud conclusively."}
