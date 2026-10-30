import hashlib
import io

import numpy as np
from PIL import Image


def finding(key, name, status="completed", flagged=False, severity="info", summary="", details=None, limitation=""):
    return {"key": key, "name": name, "status": status, "flagged": flagged, "severity": severity,
            "summary": summary, "details": details or {}, "limitation": limitation}


def not_applicable(key, name, why):
    return finding(key, name, status="not_applicable", summary=why)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(img: Image.Image, size: int = 16) -> str:
    """Difference hash (size*size bits) as hex. Used only for near-duplicate indication."""
    g = np.asarray(img.convert("L").resize((size + 1, size), Image.LANCZOS), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):0{size * size // 4}x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1") if a and b and len(a) == len(b) else 999


def png_bytes(arr_or_img) -> bytes:
    img = arr_or_img if isinstance(arr_or_img, Image.Image) else Image.fromarray(arr_or_img)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
