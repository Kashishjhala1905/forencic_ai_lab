"""Usage (from backend/):  python generate_samples.py   -> writes ../sample_documents/"""
from pathlib import Path

from app.utils.synthetic import generate_all

if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "sample_documents"
    for p in generate_all(out):
        print("created", p.name)
