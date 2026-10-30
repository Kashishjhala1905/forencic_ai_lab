"""SQLite persistence (stdlib sqlite3). Chosen over MongoDB for zero-configuration reliability on Windows."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
  original_filename TEXT NOT NULL, stored_path TEXT NOT NULL, file_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, phash TEXT, page_count INTEGER,
  width INTEGER, height INTEGER, doc_type_selected TEXT NOT NULL DEFAULT 'auto',
  status TEXT NOT NULL DEFAULT 'uploaded', latest_analysis_id TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_doc_user ON documents(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_doc_hash ON documents(user_id, sha256);
CREATE TABLE IF NOT EXISTS analyses (
  id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id), user_id TEXT NOT NULL,
  status TEXT NOT NULL, stage TEXT, progress INTEGER DEFAULT 0, error TEXT,
  created_at TEXT NOT NULL, completed_at TEXT,
  doc_type TEXT, doc_number TEXT, text TEXT, ocr TEXT, fields TEXT, forensic TEXT,
  validation TEXT, features TEXT, risk TEXT, category TEXT, score REAL,
  tech_confidence REAL, requires_review INTEGER DEFAULT 0, heatmap_path TEXT);
CREATE INDEX IF NOT EXISTS ix_an_user ON analyses(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_an_docnum ON analyses(user_id, doc_number);
CREATE INDEX IF NOT EXISTS ix_an_doc ON analyses(document_id);
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, user_id TEXT NOT NULL,
  path TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, action TEXT NOT NULL,
  document_id TEXT, detail TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_audit_user ON audit_events(user_id, id);
"""

JSON_COLS = {"ocr", "fields", "forensic", "validation", "features", "risk"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db():
    """Transactional connection: commits on success, rolls back (and re-raises) on failure."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as c:
        c.executescript(SCHEMA)


def row_to_dict(row) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in JSON_COLS:
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                d[k] = None
    return d
