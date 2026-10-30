# Architecture

```
frontend (React/Vite)  --Bearer JWT-->  FastAPI routers (app/api)
                                         ├─ auth.py        register / login (throttled) / me / change-password
                                         ├─ documents.py   upload (magic-byte sniff, size cap, readability check), list, details, preview, analyze, delete
                                         ├─ analysis.py    results, ELA heatmap, PDF report
                                         ├─ dashboard.py   stats / recent / admin overview (role-checked)
                                         └─ health.py      DB + OCR status
services/pipeline.py (BackgroundTask):
  text_acquisition (PyMuPDF text → Tesseract fallback) → fields (field_rules.py regex tiers) → forensic (image_forensics / pdf_forensics)
  → duplicate checks (SHA-256, document number, dHash) → validation.py → ml/risk.py (score, confidence, anomaly) → persist
storage/: uploads/<user_id>/<uuid>.<ext>, heatmaps/, reports/, forensic.db (SQLite)
```
Tables: users, documents, analyses (JSON columns: ocr, fields, forensic, validation, features, risk), reports, audit_events. Indexed on owner/time, hash, document number.

**Security controls.** bcrypt hashes; JWT (HS256, expiring, secret from env); every document/analysis query is filtered by `user_id`, other users' IDs return 404; upload type decided by file *content*, size streamed against a cap, decompression-bomb pixel cap, generated storage names (original name is display-only and sanitised), password-protected/corrupt files rejected; uploaded files are never executed and PDFs are never served raw (preview is a server-rendered PNG); extracted text is escaped in the React UI and XML-escaped in reports; CORS allow-list from env; `nosniff`/`X-Frame-Options` headers; login throttling; audit log never stores passwords, tokens or document text; failures surface as errors (a failed save returns 500, a failed analysis is stored as `failed` with a message).

**Retention.** Documents are kept until the owner deletes them. Delete removes the stored file, heatmaps, generated reports, analyses and report rows. Audit events are retained (they contain the action, the user, the document id and, for deletions, the filename).

**Tokens** are kept in `localStorage` (simple, but readable by any XSS); for a hardened deployment move to httpOnly cookies + CSRF protection and serve over HTTPS.
