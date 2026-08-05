"""Pure-function tests for the PDF invoice parser (no DB fixtures needed)."""

from decimal import Decimal

from balance360.services.pdf_invoice import (
    _extract_items,
    _extract_pos_number,
    _extract_voucher_type,
    _to_decimal,
)

# Literal pdfplumber output from a real Dux Software invoice (EVER/EMVI).
DUX_LINES = [
    "Código Descripción Cant. Precio Uni. Sub Total % Sub Total c/",
    "IVA IVA",
    "813 PANTALLA 15.6 LED 1366X768 HD 30PIN SLIM N156BGA-EA3 1,00 79.140,50 79.140,50 21,00 95.760,00",  # noqa: E501
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


# Literal pdfplumber output from a real Prosegur service invoice (2026-05).
# Service-invoice shape: description + one $ amount, no qty/unit-price/IVA columns.
PROSEGUR_LINES = [
    "CONCEPTO Cantidad Importe",
    "ABONO JUNIO 2026",
    "Periodo: 01/06/2026 - 30/06/2026",
    "Solicitud Servicio: I1629052.2",
    "Dir. Servicio: AROMA 2312 1406 CAPITAL FEDERAL CAPITAL FEDERAL",
    "ABONO SMART INICIAL CASA $ 71.548,90",
    "VISITA ACUDA VIVIENDA 3 OPERATIVOS $ 11.790,87",
    "SERVICE CASA $ 17.954,08",
    "DESCUENTO POR CONTENCION - 1 LINEA POR 6 MESES $ -8.977,04",
    "DESCUENTO POR CONTENCION - 1 LINEA POR 6 MESES $ -35.774,45",
    "DESCUENTO POR CONTENCION - 1 LINEA POR 6 MESES $ -5.895,44",
    "SUBTOTAL $ 50.646,92",
    "IB CABA 1,00% $ 506,47",
    "IVA 21% $ 10.635,85",
]


def test_concepto_importe_extracts_items():
    items = _extract_items(PROSEGUR_LINES, "A")
    assert len(items) == 6
    first = items[0]
    assert first.description == "ABONO SMART INICIAL CASA"
    assert first.quantity == Decimal("1")
    assert first.unit_price == Decimal("71548.90")
    assert first.iva_rate == Decimal("21")  # voucher-A default, no IVA column


def test_concepto_importe_keeps_negative_discounts():
    items = _extract_items(PROSEGUR_LINES, "A")
    discounts = [i for i in items if i.unit_price < 0]
    assert len(discounts) == 3
    assert discounts[0].unit_price == Decimal("-8977.04")
    # Including the discounts, the line sum reproduces the printed SUBTOTAL.
    assert sum(i.unit_price * i.quantity for i in items) == Decimal("50646.92")


def test_concepto_importe_skips_metadata_and_totals():
    items = _extract_items(PROSEGUR_LINES, "A")
    joined = " ".join(i.description for i in items)
    assert "Periodo" not in joined
    assert "SUBTOTAL" not in joined
    assert "IB CABA" not in joined


def test_to_decimal_sign_handling():
    assert _to_decimal("-8.977,04") == Decimal("-8977.04")
    assert _to_decimal("$ -35.774,45") == Decimal("-35774.45")
    assert _to_decimal("8.977,04-") == Decimal("-8977.04")  # trailing-minus ERPs
    assert _to_decimal("1.234,56") == Decimal("1234.56")  # positive unchanged
