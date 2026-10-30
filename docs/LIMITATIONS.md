# Limitations and unresolved items

**Techniques**
* **ELA** only applies to JPEG; it compares recompression error with comparable regions (edge-density-matched textured blocks, and flat blocks among themselves). Re-saves, resizing, screenshots and heavy compression also trigger it. It did **not** detect a splice into a perfectly noise-free synthetic page (no compression-history difference exists there); it did flag a splice into a noisy synthetic scan. Not applicable to PNG/PDF (reported as such, no heatmap is produced).
* **Metadata** (EXIF/PDF) is trivially edited or stripped. Absence proves nothing.
* **PDF checks** (revisions, active content, annotations, font mix) are weak indicators; signed or form-filled PDFs legitimately show revisions. Object-stream content may be missed by the active-content scan. Embedded images inside PDFs are not individually analysed.
* **Near-duplicate detection** uses a 16×16 dHash of page 1 and will match different documents made from the same template (low weight, informational).
* **Copy-move detection, font/glyph forensics on scans, signature verification, face/hologram/MRZ checks and template matching are not implemented.**

**Extraction**
* Regex rules target English labels ("Invoice No", "Date of Issue"…). Other languages/layouts need new rules in `field_rules.py`. Numeric dates are read day-first (flagged as ambiguous when d/m is unclear). OCR runs with `--psm 6` and light preprocessing; poor scans give poor text and lower technical confidence.
* Duplicate checks compare only within one user's documents (by design, for privacy); the *first* document of a duplicate pair is not retro-flagged.

**Engineering**
* Analysis runs as a FastAPI background task inside the API process (no external queue); a server restart mid-analysis leaves it `processing`. Login throttle is in-memory and per-process.
* The UI was verified by building it, by Vitest component tests, and by exercising the same API calls over HTTP; it was **not** visually inspected in a real browser in the development environment. Please review layouts on your machine.
* SQLite is used instead of MongoDB. Synthetic-document results prove only that the software works as specified, not real-world accuracy.
* `npm audit` reports advisories in dev tooling dependencies; they were not force-upgraded.
