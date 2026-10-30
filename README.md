# Forensic AI Lab — Intelligent Document Fraud Detection System

A local, web-based system that ingests PDFs/images, extracts text (PDF text layer or Tesseract OCR), pulls out fields, runs
cross-field validation and image/PDF forensic checks, and produces an **explainable risk indicator** plus a downloadable PDF report.

> **Important.** Output is a set of *indicators for human review*. A high score is not proof of fraud and a low score is not proof of
> authenticity. The score is a rule-weighted sum, **not a probability**. No model is trained on invented labels.

**Stack:** React + Vite + Tailwind v4 + React Router + Axios + Recharts + Lucide · FastAPI + Uvicorn + Pydantic · PyMuPDF, Pillow, OpenCV,
pytesseract · scikit-learn (IsolationForest, context only) · **SQLite** (zero-config; chosen over MongoDB as the most reliable setup on Windows) · ReportLab · pytest / Vitest.
Everything runs locally; no paid APIs or cloud services.

## 1. Prerequisites (Windows 10/11, PowerShell, VS Code)

| Tool | Version | Check |
|---|---|---|
| Python | 3.10 – 3.13 (64-bit) | `python --version` |
| Node.js (includes npm) | 18 or newer (20/22 LTS recommended) | `node --version` ; `npm --version` |
| Tesseract OCR | 5.x | `& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version` |

Install if missing: Python from python.org (tick **Add python.exe to PATH**), Node LTS from nodejs.org, and Tesseract from the
UB Mannheim Windows installer (<https://github.com/UB-Mannheim/tesseract/wiki>). Tesseract is optional for PDFs that contain a text layer but
**required for images and scanned PDFs**. If a command is "not recognized", close and reopen the terminal after installing; if `python` opens the
Microsoft Store, use `py --version` / `py -m venv` instead.

## 2. Backend setup (Terminal 1)

```powershell
cd forensic-ai-lab\backend
python -m venv .venv
# If activation is blocked:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"      # paste the output as JWT_SECRET in .env
```

Edit `backend\.env`: set `JWT_SECRET`; if Tesseract is not on PATH set  
`TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`; optionally `ADMIN_EMAILS=you@example.com` (that e-mail gets the admin role when it registers).

Start the API:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Check: <http://localhost:8000/api/health> must return `"status":"ok"` and show whether OCR is available. Interactive API docs: <http://localhost:8000/docs>.

## 3. Frontend setup (Terminal 2)

```powershell
cd forensic-ai-lab\frontend
npm install
Copy-Item .env.example .env       # VITE_API_BASE_URL=http://localhost:8000  (no trailing slash, no /api)
npm run dev
```

Open <http://localhost:5173>, create an account, and upload a file. If you change the frontend port/host, add it to `CORS_ORIGINS` in `backend\.env` and restart the API.

## 4. Sample (synthetic) documents

```powershell
cd backend ; python generate_samples.py       # writes ..\sample_documents\
```

Creates **synthetic** test files (normal invoice, inconsistent dates, total mismatch, missing field, duplicate invoice number, noisy-scan JPEG with and without a
pasted patch, PDF with an "Adobe Photoshop" producer). They are labelled fake test data, not real fraudulent documents. To see duplicate detection, upload
`01_normal_invoice.pdf` first, then `05_duplicate_identifier_invoice.pdf` (duplicates are checked against *your own* earlier documents only).

## 5. Tests

```powershell
cd backend ; python -m pytest -q          # 59 tests: auth, ownership, upload validation, pipeline, forensics, scoring, reports
cd ..\frontend ; npm test ; npm run build
```
OCR-dependent tests are skipped automatically if Tesseract is absent. Test results on synthetic documents verify that the software behaves as specified;
**they do not measure real-world fraud-detection accuracy.**

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `python`/`pip`/`npm` not recognized | Reinstall with "Add to PATH", reopen terminal; use `py -m ...` for Python. |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| Health shows `"ocr":{"available":false}` | Install Tesseract and/or set `TESSERACT_CMD`; restart the API. |
| Frontend: "Cannot reach the backend…" | API not running, wrong `VITE_API_BASE_URL`, or origin missing from `CORS_ORIGINS`. Restart both after editing env files. |
| `Port 8000/5173 already in use` | `netstat -ano \| findstr :8000` then `taskkill /PID <pid> /F`, or choose another port (and update env files). |
| Everyone logged out after restarting API | `JWT_SECRET` is empty (random per start). Set it in `.env`. |
| `pip` build errors | Use 64-bit Python 3.10–3.13 (wheels exist for all dependencies); don't use pre-release Python. |
| Login blocked for ~5 min | Throttle after 5 failed attempts per email+IP. |
| Database | SQLite file at `storage\forensic.db` (override with `DATABASE_PATH`). Delete it to reset all data. |

## 7. Documentation
* `docs/ARCHITECTURE.md` — modules, data flow, API, data retention, security controls
* `docs/RISK_SCORING.md` — weights, thresholds, configuration, meaning of each outcome
* `docs/LIMITATIONS.md` — what each technique can and cannot do, and known gaps
