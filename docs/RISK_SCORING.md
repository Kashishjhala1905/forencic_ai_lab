# Risk scoring

**Two separate numbers are reported.**
* **Risk indicator score (0–100)** – sum of points for indicators that fired (validation rules that *failed* and forensic checks that were *flagged*), capped at 100. Not a probability.
* **Technical confidence (0–100)** – how much evidence the system could evaluate: 40 % text quality (amount of text × OCR confidence), 30 % forensic-check coverage, 30 % share of validation rules that could be evaluated (pass/fail rather than not-applicable). It says nothing about fraud.

**Outcomes** (`thresholds`, `insufficient` in config):
1. `score ≥ high (50)` → **HIGH RISK** (even when confidence is low: strong evidence is never hidden).
2. else if technical confidence `< 35` or extracted text `< 30` characters → **INSUFFICIENT EVIDENCE / MANUAL REVIEW** (a blank or unreadable file is never "low risk").
3. else `score ≥ medium (20)` → **MEDIUM RISK**; otherwise **LOW RISK**.
"Requires manual review" = any outcome other than LOW.

**Default points** (see `backend/app/ml/risk.py → DEFAULT_CONFIG`): expiry before issue 35 · DOB implausible/after issue 35 · subtotal+tax≠total 35 · duplicate document number 25 · conflicting values 20 · issue date in future 15 · invalid date 10 · missing mandatory fields 8–14 (+3 per extra) · due before invoice 8 · editing-software metadata 20 (low 6) · ELA outliers 18 (low 8) · PDF incremental updates 5–12 · PDF active content 15 · overlay annotations 5 · numeric-font mismatch/hidden text 6 · identical re-upload 4 · near-identical page image 3. Informational facts (e.g. a document has expired, missing EXIF) are shown but **not scored**.

**Override** by pointing `RISK_CONFIG_PATH` at a JSON file containing only the keys to change, e.g. `{"thresholds": {"high": 40}, "points": {"duplicate_file": 0}}`. Restart the API.

**Anomaly model.** An IsolationForest is fitted *only* on feature vectors of the user's own earlier analyses and only once ≥ 30 exist; it reports how atypical the new document is compared with that history. Missing features are imputed with the column median. Its default weight is `0`, so it is shown for context and does not change the score. It is unsupervised: it was not trained on any fraud labels and its output must not be read as fraud probability.

**Calibration disclosure.** Points and thresholds are expert-set heuristics. The ELA thresholds were tuned against a handful of synthetic scans only. They have not been validated or calibrated against real fraud data; do so before relying on them.
