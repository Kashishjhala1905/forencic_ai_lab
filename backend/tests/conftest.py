import itertools
import os
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="forensic-tests-")
os.environ.update({"STORAGE_DIR": _TMP, "DATABASE_PATH": str(Path(_TMP) / "test.db"), "JWT_SECRET": "test-secret-not-for-production-0123456789",
                   "CORS_ORIGINS": "http://localhost:5173", "ADMIN_EMAILS": "admin@example.com", "MAX_UPLOAD_MB": "2"})

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.text_acquisition import ocr_status  # noqa: E402
from app.utils import synthetic  # noqa: E402

OCR = ocr_status()["available"]
needs_ocr = pytest.mark.skipif(not OCR, reason="Tesseract OCR is not installed")
_counter = itertools.count(1)


@pytest.fixture(scope="session")
def client():
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    d = tmp_path_factory.mktemp("samples")
    synthetic.generate_all(d)
    return d


class User:
    def __init__(self, client, email=None, name="Test User", password="correct-horse-1"):
        self.client, self.password = client, password
        self.email = email or f"user{next(_counter)}@example.com"
        r = client.post("/api/auth/register", json={"email": self.email, "name": name, "password": password})
        assert r.status_code == 201, r.text
        self.token = r.json()["access_token"]
        self.id = r.json()["user"]["id"]
        self.h = {"Authorization": f"Bearer {self.token}"}

    def upload(self, path_or_bytes, name=None, doc_type="auto"):
        if isinstance(path_or_bytes, (str, Path)):
            name = name or Path(path_or_bytes).name
            data = Path(path_or_bytes).read_bytes()
        else:
            data = path_or_bytes
        return self.client.post("/api/documents/upload", headers=self.h, files={"file": (name or "x.bin", data)}, data={"doc_type": doc_type})

    def analyze(self, path, doc_type="auto"):
        """Upload + analyze (background task runs synchronously under TestClient). Returns full analysis dict."""
        r = self.upload(path, doc_type=doc_type); assert r.status_code == 201, r.text
        did = r.json()["id"]
        r = self.client.post(f"/api/documents/{did}/analyze", headers=self.h); assert r.status_code == 202, r.text
        a = self.client.get(f"/api/analysis/{r.json()['analysis_id']}", headers=self.h).json()
        assert a["status"] == "completed", a.get("error")
        a["_doc_id"] = did
        return a


@pytest.fixture
def user(client):
    return User(client)


@pytest.fixture
def make_user(client):
    return lambda **kw: User(client, **kw)


def rule(a, name):
    return next(v for v in a["validation"] if v["rule"] == name)
