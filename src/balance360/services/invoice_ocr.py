"""Reading scanned invoices (PDFs without a text layer, and photos).

Same approach as AutoFiller (`servidor/extraccion/ocr.py`), measured there against 63 real
invoices: Google Cloud Vision returns text that the very same regexes parse, so a scan does
not need a parser of its own — it only needs its text. The OCR text goes through
`parse_invoice_text`, the function the text-layer path uses, which means every layout added
for PDFs also reads scans and every scan is checked by the same `lines_gap`.

Decisions worth knowing:

- **REST + API key + stdlib `urllib`**, no Google SDK: the SDK wants a service account and
  drags dependencies in, while a key and ~20 lines are enough.
- **No key, no OCR, and no error**: `parse_invoice_file` returns the text-layer result with
  `needs_manual_items` set, exactly what the app did before this module existed.
- **An OCR read is never trusted on its own.** OCR confuses a `5` with a `6` and nothing
  complains; the only defence is the printed total. `parse_invoice_file` only reports what it
  read; whoever loads it must call `is_verified` first (the historical import does).
- **Only page 1**, like AutoFiller. An invoice that spills onto a second page leaves lines
  unread, and that shows up as a non-zero `lines_gap`, not as a silent wrong load.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from balance360.services.pdf_invoice import ParsedInvoice, parse_invoice_text, pdf_text

logger = logging.getLogger(__name__)

VISION_URL = "https://vision.googleapis.com/v1/images:annotate"
# DOCUMENT_TEXT_DETECTION is the variant for dense, structured documents;
# TEXT_DETECTION is meant for street signs.
FEATURE = "DOCUMENT_TEXT_DETECTION"
# 200 dpi gives an A4 long side of 2339 px, which is what AutoFiller measured. Phone photos
# are much bigger than needed, so they are shrunk to MAX_SIDE; nothing is ever enlarged.
RASTER_DPI = 200
MAX_SIDE = 3000
JPEG_QUALITY = 90
TIMEOUT_SECONDS = 60

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


class OcrUnavailable(RuntimeError):
    """No API key configured."""


def ocr_available() -> bool:
    return bool(os.environ.get("GOOGLE_VISION_API_KEY"))


def rasterize_first_page(pdf_bytes: bytes) -> Any:
    """PIL image of page 1 of a PDF."""
    import pypdfium2

    document = pypdfium2.PdfDocument(io.BytesIO(pdf_bytes))
    try:
        return document[0].render(scale=RASTER_DPI / 72).to_pil()
    finally:
        document.close()


def _to_jpeg(image: Any) -> bytes:
    from PIL import Image

    image = image.convert("RGB")
    longest = max(image.size)
    if longest > MAX_SIDE:
        scale = MAX_SIDE / longest
        image = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def ocr_text(image: Any) -> str:
    """Full text of the image according to Cloud Vision.

    Raises OcrUnavailable without a key and RuntimeError if Google answers an error.
    """
    key = os.environ.get("GOOGLE_VISION_API_KEY")
    if not key:
        raise OcrUnavailable("GOOGLE_VISION_API_KEY is not set")

    body = json.dumps(
        {
            "requests": [
                {
                    "image": {"content": base64.b64encode(_to_jpeg(image)).decode("ascii")},
                    "features": [{"type": FEATURE}],
                    # Without the hint the OCR sometimes "corrects" words into English.
                    "imageContext": {"languageHints": ["es"]},
                }
            ]
        }
    ).encode("utf-8")
    # The key goes in a header, not the query string: a URL ends up in logs and proxies.
    request = urllib.request.Request(
        VISION_URL,
        data=body,
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"Cloud Vision answered {e.code}: {detail}") from None

    first = (data.get("responses") or [{}])[0]
    if "error" in first:
        raise RuntimeError(f"Cloud Vision: {first['error'].get('message')}")
    return str((first.get("fullTextAnnotation") or {}).get("text", ""))


def _open_image(content: bytes) -> Any:
    from PIL import Image

    return Image.open(io.BytesIO(content))


def parse_invoice_file(name: str, content: bytes) -> ParsedInvoice:
    """Parse a PDF (text layer or scan) or a photo. Never raises for unreadable input.

    - PDF with text  -> the text-layer path, unchanged.
    - PDF without it -> page 1 rasterized and OCR'd.
    - Image          -> OCR'd.
    OCR failures (no key, network, bad image) are logged and leave the invoice for manual
    entry, because an import of thousands of files must not die on one bad scan.
    """
    extension = os.path.splitext(name)[1].lower()
    is_pdf = extension == ".pdf"
    if is_pdf:
        text = pdf_text(content)
        if text.strip():
            return parse_invoice_text(text)
    elif extension not in IMAGE_EXTENSIONS:
        return parse_invoice_text("")

    if not ocr_available():
        return parse_invoice_text("")
    try:
        image = rasterize_first_page(content) if is_pdf else _open_image(content)
        text = ocr_text(image)
    except Exception as e:  # noqa: BLE001 - see docstring
        logger.warning("OCR failed for %s: %s", name, e)
        return parse_invoice_text("")
    parsed = parse_invoice_text(text)
    parsed.source = "ocr"
    return parsed
