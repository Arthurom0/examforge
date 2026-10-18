"""PDF text extraction with PyMuPDF, falling back to Tesseract OCR for scanned pages."""
from __future__ import annotations

import io
import logging
import re
import os
import shutil
from dataclasses import dataclass

import pymupdf as fitz

from ..config import settings

log = logging.getLogger(__name__)

# A page with fewer extractable characters than this is treated as scanned.
MIN_TEXT_CHARS = 40
OCR_DPI = 300

LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}

# Glyph substitutions for symbols that math fonts often map to private-use or odd code points.
MATH_FIXES = {
    "": "μ", "": "ρ", "": "ν", "": "α", "": "β", "": "γ",
    "": "δ", "": "Δ", "": "θ", "": "λ", "": "π", "": "σ",
    "": "τ", "": "ω", "": "Ω", "": "∂", "": "∇", "": "∫",
    "": "∑", "": "×", "": "≈", "": "≤", "": "≥", "": "→",
    "": "−", "": "°", "": "·",
}


@dataclass
class PageText:
    page: int  # 1-based
    text: str
    ocr: bool = False


# GUI apps on macOS don't get the shell PATH, so look where Homebrew/MacPorts install Tesseract.
_TESSERACT_CANDIDATES = ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/opt/local/bin/tesseract",
                         r"C:\Program Files\Tesseract-OCR\tesseract.exe")


def tesseract_path() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    return next((c for c in _TESSERACT_CANDIDATES if os.path.exists(c)), None)


def ocr_available() -> bool:
    return tesseract_path() is not None


def clean_text(text: str) -> str:
    for src, dst in {**LIGATURES, **MATH_FIXES}.items():
        text = text.replace(src, dst)
    text = text.replace(" ", " ").replace("\r", "")
    # Re-join words hyphenated across line breaks ("écoule-\nment" -> "écoulement").
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _ocr_page(page: fitz.Page) -> str:
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = tesseract_path() or "tesseract"

    pix = page.get_pixmap(dpi=OCR_DPI)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    # psm 6 = assume a uniform block of text; keeps equation lines together better than auto.
    raw = pytesseract.image_to_string(img, lang=settings.ocr_langs, config="--psm 6")
    return _normalize_ocr_math(raw)


def _normalize_ocr_math(text: str) -> str:
    """Best-effort repair of common OCR mistakes around equations and units."""
    fixes = [
        (r"(?<=\d)\s*[xX×]\s*10\s*[-−]\s*(\d+)", r" × 10^-\1"),  # 3 x 10-5 -> 3 × 10^-5
        (r"(?<=\d)\s*[xX×]\s*10\s*(\d)\b", r" × 10^\1"),
        (r"\bm\s*/\s*s2\b", "m/s²"),
        (r"\bm2\b", "m²"),
        (r"\bm3\b", "m³"),
        (r"\bkg\s*/\s*m3\b", "kg/m³"),
        (r"(?<=\d)\s*°\s*C\b", " °C"),
        (r"\bPa\.s\b", "Pa·s"),
    ]
    for pattern, repl in fixes:
        text = re.sub(pattern, repl, text)
    return text


def extract_pdf(path: str) -> list[PageText]:
    pages: list[PageText] = []
    can_ocr = ocr_available()
    with fitz.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text", sort=True)
            used_ocr = False
            if len(text.strip()) < MIN_TEXT_CHARS and page.get_images():
                if can_ocr:
                    try:
                        text = _ocr_page(page)
                        used_ocr = True
                    except Exception as exc:  # language pack missing, etc.
                        log.warning("OCR failed on page %s: %s", i, exc)
                else:
                    log.warning("Page %s looks scanned but tesseract is not installed", i)
            pages.append(PageText(page=i, text=clean_text(text), ocr=used_ocr))
    return pages


def render_page_png(path: str, page_number: int, dpi: int = 150) -> bytes:
    with fitz.open(path) as doc:
        return doc[page_number - 1].get_pixmap(dpi=dpi).tobytes("png")


def chunk_pages(pages: list[PageText], size: int = 1200, overlap: int = 200) -> list[tuple[int, str]]:
    """Split page text into overlapping windows, breaking on paragraph/sentence boundaries."""
    chunks: list[tuple[int, str]] = []
    for p in pages:
        text = p.text
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):
                window = text[start:end]
                cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
                if cut > size // 2:
                    end = start + cut + 1
            piece = text[start:end].strip()
            if len(piece) > 30:
                chunks.append((p.page, piece))
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks
