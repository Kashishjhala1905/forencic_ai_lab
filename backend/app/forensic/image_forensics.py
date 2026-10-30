"""Explainable image-forensics checks. Every result is an *indicator*, never proof of manipulation."""
import io
import re
from datetime import datetime

import cv2
import numpy as np
from PIL import Image, ImageChops
from PIL.ExifTags import TAGS

from .common import finding, not_applicable, png_bytes

EDITORS = re.compile(r"photoshop|gimp|canva|paint\.net|pixlr|lightroom|snapseed|affinity|illustrator|inkscape|picsart|fotor|photopea|corel", re.I)
BLOCK = 32


def _exif_dates(exif) -> dict:
    ifd = exif.get_ifd(0x8769) if hasattr(exif, "get_ifd") else {}
    return {"DateTime": exif.get(306), "DateTimeOriginal": ifd.get(36867), "DateTimeDigitized": ifd.get(36868)}


def _parse_exif_dt(s):
    try:
        return datetime.strptime(str(s).strip()[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def format_inspection(img: Image.Image, path: str) -> dict:
    w, h = img.size
    dpi = img.info.get("dpi")
    small = min(w, h) < 600
    return finding("image_format", "Image format & dimensions", flagged=False, severity="info",
                   summary=f"{img.format} image, {w}×{h}px, mode {img.mode}" + (", low resolution for OCR/forensics" if small else ""),
                   details={"format": img.format, "width": w, "height": h, "mode": img.mode,
                            "dpi": [round(float(d)) for d in dpi] if dpi else None, "low_resolution": small},
                   limitation="Resolution below ~600px on the short side reduces OCR and forensic reliability.")


def metadata_inspection(img: Image.Image) -> dict:
    exif = img.getexif()
    info = {k: str(v)[:120] for k, v in img.info.items() if isinstance(v, (str, int, float)) and k.lower() in
            ("software", "creation time", "author", "comment", "description", "title", "source")}
    tags = {TAGS.get(k, str(k)): str(v)[:120] for k, v in exif.items() if isinstance(v, (str, int, float))}
    software = tags.get("Software") or info.get("Software") or info.get("software")
    issues, severity = [], "info"
    if software and EDITORS.search(software):
        issues.append(f"Image was last saved by editing software ('{software}')."); severity = "medium"
    dts = _exif_dates(exif)
    mod, orig = _parse_exif_dt(dts["DateTime"]), _parse_exif_dt(dts["DateTimeOriginal"])
    if mod and orig and abs((mod - orig).total_seconds()) > 60:
        issues.append(f"EXIF modification time ({mod}) differs from original capture time ({orig}).")
        severity = "medium" if severity == "medium" else "low"
    if mod and mod > datetime.now():
        issues.append("EXIF date is in the future."); severity = "medium"
    has_meta = bool(tags or info)
    summary = "; ".join(issues) if issues else ("No suspicious metadata found." if has_meta else
              "No EXIF/metadata present (common for scans, screenshots and messaging apps; not suspicious by itself).")
    return finding("image_metadata", "Image metadata inspection", flagged=bool(issues), severity=severity if issues else "info",
                   summary=summary, details={"software": software, "dates": {k: v and str(v) for k, v in dts.items()},
                                             "tags": dict(list(tags.items())[:25]), "format_info": info, "has_metadata": has_meta},
                   limitation="Metadata is trivially edited or stripped. Absence of metadata proves nothing; presence of editor tags only shows software use.")


def quality_analysis(img: Image.Image) -> dict:
    g = np.asarray(img.convert("L"))
    blur = float(cv2.Laplacian(g, cv2.CV_64F).var())
    qt = getattr(img, "quantization", None)
    est_q = None
    if qt and 0 in qt:
        avg = float(np.mean(qt[0]))
        est_q = int(round(max(1, min(100, 100 - avg * 1.5 if avg < 40 else 5000 / (avg * 2 + 1)))))
    notes = []
    if blur < 50: notes.append("image appears blurry/low-sharpness")
    if g.mean() < 60: notes.append("image is very dark")
    if g.std() < 25: notes.append("very low contrast")
    if est_q is not None and est_q < 50: notes.append(f"heavy JPEG compression (est. quality≈{est_q})")
    return finding("image_quality", "Image quality & compression", flagged=False, severity="info",
                   summary="; ".join(notes).capitalize() + "." if notes else "Image quality adequate for analysis.",
                   details={"sharpness_laplacian_var": round(blur, 1), "mean_brightness": round(float(g.mean()), 1),
                            "contrast_std": round(float(g.std()), 1), "estimated_jpeg_quality": est_q, "quality_issues": notes},
                   limitation="Quality estimates are heuristics; poor quality lowers technical confidence but is not a fraud signal.")


def ela_analysis(img: Image.Image, fmt: str):
    """Error Level Analysis. Returns (finding, heatmap_png | None)."""
    name = "Error Level Analysis (ELA)"
    if fmt != "JPEG":
        return not_applicable("ela", name, f"ELA relies on JPEG recompression and is not applicable to {fmt or 'this'} images."), None
    rgb = img.convert("RGB")
    buf = io.BytesIO(); rgb.save(buf, "JPEG", quality=90); buf.seek(0)
    re_img = Image.open(buf).convert("RGB")
    diff = np.asarray(ImageChops.difference(rgb, re_img), dtype=np.float32).mean(axis=2)
    h, w = diff.shape
    gray = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2GRAY)
    edges = (cv2.Canny(gray, 80, 160) > 0).astype(np.float32)
    ys, xs = h // BLOCK, w // BLOCK
    if ys < 2 or xs < 2:
        return not_applicable("ela", name, "Image too small for block-level ELA."), None
    ela_b = diff[:ys * BLOCK, :xs * BLOCK].reshape(ys, BLOCK, xs, BLOCK).mean(axis=(1, 3))
    edge_b = edges[:ys * BLOCK, :xs * BLOCK].reshape(ys, BLOCK, xs, BLOCK).mean(axis=(1, 3))
    textured = edge_b > 0.01
    flat = ~textured
    flagged_blocks = []

    def outliers(mask, label, abs_floor):
        """Two-sided robust z-test of block ELA against peers (same texture class)."""
        if mask.sum() < 8:
            return
        med = np.median(ela_b[mask])
        mad = max(np.median(np.abs(ela_b[mask] - med)) * 1.4826, 0.05 * med, 0.02)
        z = (ela_b - med) / mad
        for (y, x) in zip(*np.where(mask & (np.abs(z) > 6) & (np.abs(ela_b - med) > abs_floor))):
            flagged_blocks.append({"x": round(x / xs, 3), "y": round(y / ys, 3), "w": round(1 / xs, 3), "h": round(1 / ys, 3),
                                   "z": round(float(z[y, x]), 1), "group": label, "direction": "higher" if z[y, x] > 0 else "lower"})

    # ELA is naturally higher on edges, so textured blocks are compared only with blocks of similar edge density;
    # flat (paper/background) blocks are compared with each other to expose regions with a different noise/compression history.
    if textured.sum() >= 16:
        bins = np.quantile(edge_b[textured], [0.25, 0.5, 0.75])
        bid = np.digitize(edge_b, bins)
        for bn in range(4):
            outliers(textured & (bid == bn), "textured", 0.5)
    outliers(flat, "flat", 0.1)
    considered = int(textured.sum() + flat.sum())
    ratio = len(flagged_blocks) / max(considered, 1)
    flagged = len(flagged_blocks) >= 4 and ratio >= 0.01
    sev = "medium" if flagged and ratio >= 0.02 else "low" if flagged else "info"
    scale = 255.0 / max(float(np.percentile(diff, 99.5)), 1.0)
    heat = cv2.applyColorMap(np.clip(diff * scale, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
    hmap = cv2.addWeighted(np.asarray(rgb), 0.35, heat, 0.65, 0)
    for fb in flagged_blocks[:25]:
        x0, y0 = int(fb["x"] * w), int(fb["y"] * h)
        cv2.rectangle(hmap, (x0, y0), (x0 + int(fb["w"] * w), y0 + int(fb["h"] * h)), (0, 255, 255), 2)
    s = (f"{len(flagged_blocks)} region(s) show recompression error that differs strongly from comparable areas ({ratio:.1%} of analysed blocks)."
         if flagged else "No localized recompression anomalies relative to comparable regions.")
    return finding("ela", name, flagged=flagged, severity=sev, summary=s,
                   details={"mean_error": round(float(diff.mean()), 2), "p99_error": round(float(np.percentile(diff, 99)), 2),
                            "flagged_blocks": len(flagged_blocks), "textured_blocks": int(textured.sum()), "flat_blocks": int(flat.sum()),
                            "flagged_ratio": round(ratio, 4), "regions": flagged_blocks[:25], "recompress_quality": 90},
                   limitation="ELA highlights differences in JPEG compression history. Re-saves, resizing, sharp edges and screenshots also produce differences; it cannot prove tampering."), png_bytes(hmap)


def analyze_image(path: str):
    """Run all image checks. Returns (findings, heatmap_png|None, dims)."""
    img = Image.open(path); img.load()
    fmt = img.format
    ela_f, heat = ela_analysis(img, fmt)
    findings = [format_inspection(img, path), metadata_inspection(img), quality_analysis(img), ela_f]
    return findings, heat, {"width": img.size[0], "height": img.size[1], "format": fmt}
