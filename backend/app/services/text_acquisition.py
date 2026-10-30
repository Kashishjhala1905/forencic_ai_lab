"""PDF text extraction + local OCR (Tesseract). Never executes file content."""
import io
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from ..core.config import get_settings
from ..utils.text import normalize_text

try:  # pymupdf >= 1.24 exposes `pymupdf`; older exposes `fitz`
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

MIN_EMBEDDED_CHARS = 30


def ocr_status() -> dict:
    s = get_settings()
    if pytesseract is None:
        return {"available": False, "reason": "pytesseract package is not installed"}
    if s.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = s.tesseract_cmd
    cmd = pytesseract.pytesseract.tesseract_cmd
    if not (shutil.which(cmd) or Path(cmd).exists()):
        return {"available": False, "reason": "Tesseract executable not found (set TESSERACT_CMD or add it to PATH)"}
    try:
        return {"available": True, "engine": f"tesseract {pytesseract.get_tesseract_version()}", "lang": s.ocr_lang}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": f"Tesseract could not start: {e}"}


def _preprocess(img: Image.Image) -> Image.Image:
    import cv2
    gray = np.asarray(img.convert("L"))
    h, w = gray.shape
    if w < 1400:  # upscale small images: Tesseract works best around 200-300 DPI
        f = 1400 / w
        gray = cv2.resize(gray, (int(w * f), int(h * f)), interpolation=cv2.INTER_CUBIC)
    return Image.fromarray(gray)


def ocr_image(img: Image.Image) -> dict:
    """Return {'text', 'words': [[word, conf], ...]} using line-structured Tesseract output."""
    s = get_settings()
    data = pytesseract.image_to_data(_preprocess(img), lang=s.ocr_lang, config="--psm 6",
                                     output_type=pytesseract.Output.DICT, timeout=90)
    lines: dict[tuple, list[str]] = {}
    words = []
    for i, t in enumerate(data["text"]):
        t = (t or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not t or conf < 0:
            continue
        lines.setdefault((data["block_num"][i], data["par_num"][i], data["line_num"][i]), []).append(t)
        words.append([t, conf])
    return {"text": "\n".join(" ".join(v) for v in lines.values()), "words": words}


def acquire_text(path: str, file_type: str) -> dict:
    """Return {'pages': [...], 'ocr': {...}, 'warnings': [...]}.  Each page: page, text, source, words, mean_conf."""
    s = get_settings()
    st = ocr_status()
    ocr = {"available": st["available"], "used": False, "engine": st.get("engine"), "reason": st.get("reason")}
    pages, warnings = [], []

    def run_ocr(img: Image.Image, n: int):
        if not st["available"]:
            warnings.append(f"Page {n}: no embedded text and OCR is unavailable ({st.get('reason')}).")
            return {"text": "", "words": []}
        try:
            ocr["used"] = True
            return ocr_image(img)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Page {n}: OCR failed ({type(e).__name__}).")
            return {"text": "", "words": []}

    if file_type == "pdf":
        with pymupdf.open(path) as doc:
            total = doc.page_count
            for i in range(min(total, s.max_pdf_pages)):
                page = doc[i]
                emb = normalize_text(page.get_text("text"))
                if len(emb) >= MIN_EMBEDDED_CHARS:
                    pages.append({"page": i + 1, "text": emb, "source": "pdf_text", "words": [], "mean_conf": None})
                    continue
                pix = page.get_pixmap(dpi=s.ocr_dpi, alpha=False)
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                r = run_ocr(img, i + 1)
                confs = [w[1] for w in r["words"]]
                pages.append({"page": i + 1, "text": normalize_text(r["text"]), "source": "ocr", "words": r["words"],
                              "mean_conf": round(float(np.mean(confs)), 1) if confs else None})
            if total > s.max_pdf_pages:
                warnings.append(f"Only the first {s.max_pdf_pages} of {total} pages were processed.")
    else:
        img = Image.open(path)
        img.load()
        r = run_ocr(img.convert("RGB"), 1)
        confs = [w[1] for w in r["words"]]
        pages.append({"page": 1, "text": normalize_text(r["text"]), "source": "ocr", "words": r["words"],
                      "mean_conf": round(float(np.mean(confs)), 1) if confs else None})

    all_words = [w for p in pages for w in p["words"]]
    confs = [w[1] for w in all_words]
    ocr.update({
        "word_count": len(all_words),
        "mean_confidence": round(float(np.mean(confs)), 1) if confs else None,
        "low_confidence_ratio": round(float(np.mean([c < 60 for c in confs])), 3) if confs else None,
        "ocr_pages": [p["page"] for p in pages if p["source"] == "ocr"],
    })
    return {"pages": pages, "ocr": ocr, "warnings": warnings}
