"""Application settings, read from environment variables / backend/.env."""
import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
log = logging.getLogger("forensic")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    app_env: str = "development"
    jwt_secret: str = ""
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_mb: int = 15
    max_pdf_pages: int = 20
    max_image_pixels: int = 50_000_000
    storage_dir: str = ""
    database_path: str = ""
    tesseract_cmd: str = ""
    ocr_lang: str = "eng"
    ocr_dpi: int = 200
    admin_emails: str = ""
    risk_config_path: str = ""
    login_max_attempts: int = 5
    login_window_seconds: int = 300

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir) if self.storage_dir else ROOT_DIR / "storage"
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()

    @property
    def db_path(self) -> Path:
        return Path(self.database_path) if self.database_path else self.storage_path / "forensic.db"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_list(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.jwt_secret:
        s.jwt_secret = secrets.token_urlsafe(48)
        log.warning("JWT_SECRET is not set: using a random per-process secret. Logins reset on restart.")
    return s
