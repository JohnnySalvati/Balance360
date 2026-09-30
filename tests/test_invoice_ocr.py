"""The scan path. Cloud Vision is never called: `ocr_text` is replaced, so these tests need
neither a key nor network and pin down the decisions around the OCR, not the OCR itself."""

import pytest

from balance360.services import invoice_ocr
from tests.test_pdf_invoice import _OCR_C_SCAN


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_VISION_API_KEY", "test-key")


@pytest.fixture
def without_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_VISION_API_KEY", raising=False)


def test_image_goes_through_ocr_and_is_marked_as_ocr(with_key, monkeypatch):
    monkeypatch.setattr(invoice_ocr, "_open_image", lambda content: object())
    monkeypatch.setattr(invoice_ocr, "ocr_text", lambda image: _OCR_C_SCAN)
    parsed = invoice_ocr.parse_invoice_file("foto.jpg", b"x")
    assert parsed.source == "ocr"
    assert (parsed.pos, parsed.number) == (3, 1333)


def test_pdf_without_text_layer_is_rasterized_and_ocrd(with_key, monkeypatch):
    monkeypatch.setattr(invoice_ocr, "pdf_text", lambda content: "")
    monkeypatch.setattr(invoice_ocr, "rasterize_first_page", lambda content: object())
    monkeypatch.setattr(invoice_ocr, "ocr_text", lambda image: _OCR_C_SCAN)
    assert invoice_ocr.parse_invoice_file("scan.pdf", b"x").source == "ocr"


def test_pdf_whose_text_already_verifies_does_not_call_the_ocr(with_key, monkeypatch):
    def boom(image):
        raise AssertionError("OCR must not run when the text layer already verifies")

    monkeypatch.setattr(invoice_ocr, "pdf_text", lambda content: _OCR_C_SCAN)
    monkeypatch.setattr(invoice_ocr, "ocr_text", boom)
    parsed = invoice_ocr.parse_invoice_file("digital.pdf", b"x")
    assert parsed.source == "text"
    assert parsed.number == 1333


def test_pdf_whose_text_does_not_verify_falls_back_to_ocr(with_key, monkeypatch):
    # Adobe Scan and similar tools embed an OCR text layer that pdfplumber pulls out with the
    # words in a wrong order, so `is_verified` is False and the parser must try Cloud Vision.
    monkeypatch.setattr(invoice_ocr, "pdf_text", lambda content: "unos\ngarabatos\nsueltos")
    monkeypatch.setattr(invoice_ocr, "rasterize_first_page", lambda content: object())
    monkeypatch.setattr(invoice_ocr, "ocr_text", lambda image: _OCR_C_SCAN)
    parsed = invoice_ocr.parse_invoice_file("adobe-scan.pdf", b"x")
    assert parsed.source == "ocr"
    assert parsed.number == 1333


def test_when_neither_text_nor_ocr_verify_the_more_complete_header_wins(with_key, monkeypatch):
    # Text got a POS/number but no CUIT nor CAE; OCR got the whole header but the totals do
    # not close (an OCR that read "1500" as "1560" would look like this). OCR wins because
    # the loader can key on the whole header and the amounts still need manual review.
    text_result = "Punto de Venta: 00003 Comp. Nro: 00001333"
    ocr_result = _OCR_C_SCAN.replace("Importe Total: $\n1500,00", "Importe Total: $\n1560,00")
    monkeypatch.setattr(invoice_ocr, "pdf_text", lambda content: text_result)
    monkeypatch.setattr(invoice_ocr, "rasterize_first_page", lambda content: object())
    monkeypatch.setattr(invoice_ocr, "ocr_text", lambda image: ocr_result)
    parsed = invoice_ocr.parse_invoice_file("scan.pdf", b"x")
    assert parsed.source == "ocr" and parsed.cae is not None


def test_without_key_a_scan_is_left_for_manual_entry(without_key, monkeypatch):
    monkeypatch.setattr(invoice_ocr, "pdf_text", lambda content: "")
    parsed = invoice_ocr.parse_invoice_file("scan.pdf", b"x")
    assert parsed.needs_manual_items and parsed.number is None


def test_ocr_failure_does_not_raise(with_key, monkeypatch):
    def fail(image):
        raise RuntimeError("Cloud Vision answered 403")

    monkeypatch.setattr(invoice_ocr, "_open_image", lambda content: object())
    monkeypatch.setattr(invoice_ocr, "ocr_text", fail)
    parsed = invoice_ocr.parse_invoice_file("foto.png", b"x")
    assert parsed.needs_manual_items


def test_unknown_extension_is_not_read(with_key):
    assert invoice_ocr.parse_invoice_file("notas.docx", b"x").needs_manual_items


def test_ocr_text_sends_the_key_in_a_header_not_in_the_url(with_key, monkeypatch):
    import io
    import json

    from PIL import Image

    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"responses": [{"fullTextAnnotation": {"text": "hola"}}]}).encode()

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["key"] = request.get_header("X-goog-api-key")
        return Response()

    monkeypatch.setattr(invoice_ocr.urllib.request, "urlopen", fake_urlopen)
    assert invoice_ocr.ocr_text(Image.new("RGB", (10, 10))) == "hola"
    assert "test-key" not in seen["url"] and seen["key"] == "test-key"
    assert io  # keep the import used
