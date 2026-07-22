"""Pure-function tests for the PDF invoice parser (no DB fixtures needed)."""
from decimal import Decimal

from balance360.services.pdf_invoice import (
    _extract_items,
    _extract_pos_number,
    _extract_voucher_type,
)

# Literal pdfplumber output from a real Dux Software invoice (EVER/EMVI).
DUX_LINES = [
    "Código Descripción Cant. Precio Uni. Sub Total % Sub Total c/",
    "IVA IVA",
    "813 PANTALLA 15.6 LED 1366X768 HD 30PIN SLIM N156BGA-EA3 1,00 79.140,50 79.140,50 21,00 95.760,00",
    "(813)",
    "SUBTOTAL: $ 79.140,50",
    "IVA 21%: $16.619,50",
]


def test_dux_layout_extracts_items():
    items = _extract_items(DUX_LINES, "A")
    assert len(items) == 1
    item = items[0]
    assert item.quantity == Decimal("1")
    assert item.unit_price == Decimal("79140.50")
    assert item.iva_rate == Decimal("21")
    assert "N156BGA-EA3" in item.description
    # "(813)" is a continuation line below the row (wrap="append").
    assert item.description.endswith("(813)")


def test_dux_stops_at_totals():
    items = _extract_items(DUX_LINES, "A")
    # SUBTOTAL / IVA lines must not become items.
    assert all("SUBTOTAL" not in i.description for i in items)


def test_pos_number_from_n_symbol():
    # Dux: "Nº 00002-00006657"
    assert _extract_pos_number([], "FACTURA\nNº 00002-00006657") == (2, 6657)
    # ssd-ml style with the letter glued to the digits.
    assert _extract_pos_number([], "Nº A00005-00024903") == (5, 24903)


def test_pos_number_ignores_remito():
    text = "REMITO: X-00002-00024415"
    assert _extract_pos_number([], text) == (None, None)


def test_voucher_type_from_afip_code_split_lines():
    # pdfplumber pushes the code to the end of the NEXT line.
    text = "AUTONOMA DE BUENOS AIRES Cod. FECHA: 13/07/2026\nTEL: 011 7522.1487 001"
    assert _extract_voucher_type(text.split("\n"), text) == "A"


def test_voucher_type_from_afip_code_inline():
    text = "Cod.\n006\nSEÑOR/ES: FULANO"
    assert _extract_voucher_type(text.split("\n"), text) == "B"


def test_voucher_type_unknown_code_is_none():
    # Fail-closed: a "Cod." followed by a non-voucher code must not invent a letter.
    text = "algo Cod. otra cosa\nzzz 099"
    assert _extract_voucher_type(text.split("\n"), text) is None
