"""Text normalisation and date/amount parsing helpers. All input is treated as untrusted."""
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CTRL.sub("", text)
    text = "\n".join(re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(raw: str) -> tuple[date | None, bool]:
    """Return (date, ambiguous). Numeric d/m vs m/d is ambiguous when both parts <= 12; day-first is assumed."""
    s = (raw or "").strip().strip(".,")
    try:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return date(int(m[1]), int(m[2]), int(m[3])), False
        m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
        if m:
            a, b, y = int(m[1]), int(m[2]), int(m[3])
            if y < 100:
                y += 2000 if y < 70 else 1900
            if a > 12:
                return date(y, b, a), False
            if b > 12:
                return date(y, a, b), False
            return date(y, b, a), a != b
        m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", s)
        if m and m[2][:3].lower() in _MONTHS:
            return date(int(m[3]), _MONTHS[m[2][:3].lower()], int(m[1])), False
        m = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", s)
        if m and m[1][:3].lower() in _MONTHS:
            return date(int(m[3]), _MONTHS[m[1][:3].lower()], int(m[2])), False
    except ValueError:
        return None, False
    return None, False


def parse_amount(raw: str) -> Decimal | None:
    s = re.sub(r"[^\d.,]", "", raw or "")
    if not s:
        return None
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def today() -> date:
    return datetime.now().date()
