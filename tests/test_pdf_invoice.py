"""Pure-function tests for the PDF invoice parser (no DB fixtures needed)."""

import datetime
from decimal import Decimal

import pytest

from balance360.services.pdf_invoice import (
    ParsedInvoice,
    ParsedInvoiceLine,
    _extract_date,
    _extract_items,
    _extract_pos_number,
    _extract_total,
    _extract_tributes_total,
    _extract_voucher_type,
    _known_supplier,
    _to_decimal,
    _totals_lines,
    lines_gap,
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


# ---------------------------------------------------------------------------
# Histórico 2025: layouts, totales de control y proveedores reconocidos.
# Los textos son salida literal de pdfplumber, recortada y con los nombres cambiados.
# ---------------------------------------------------------------------------
PORTAL_B_LINES = [
    "Código Producto / Servicio Cantidad U. Medida Precio Unit. % Bonif Imp. Bonif. Subtotal",
    "Servicio de ejemplo 1,00 unidades 204664,00 0,00 0,00 204664,00",
    "Otro servicio 2,00 unidades 100,00 0,00 0,00 200,00",
    "Subtotal: $ 204864,00",
    "Importe Total: $ 204864,00",
]


def test_portal_b_layout_has_no_iva_column():
    items = _extract_items(PORTAL_B_LINES, "B")
    assert [(i.description, i.quantity, i.unit_price) for i in items] == [
        ("Servicio de ejemplo", Decimal("1"), Decimal("204664.00")),
        ("Otro servicio", Decimal("2"), Decimal("100.00")),
    ]


def test_portal_a_layout_accepts_comma_decimal_iva():
    lines = [
        "Código Producto / Servicio Cantidad U. medida Precio Unit. % Bonif Subtotal "
        "Subtotal c/IVA",
        "SSD de ejemplo 1,00 unidades 121500,00 0,00 121500,00 10,5% 134257,50",
        "Honorarios 1,00 unidades 125000,00 0,00 125000,00 21% 151250,00",
        "Importe Total: $ 285507,50",
    ]
    items = _extract_items(lines, "A")
    assert [i.iva_rate for i in items] == [Decimal("10.5"), Decimal("21")]


def test_todovision_layout():
    lines = [
        "CODIGO DETALLE CANT DESPACHO Porc. IVA P.U.$ P.TOT.$",
        "W10288N PLACA DE EJEMPLO USB T 1.00 10.50 18098.640 18098.64",
        "Son VEINTE MIL",
    ]
    (item,) = _extract_items(lines, "A")
    assert (item.quantity, item.unit_price, item.iva_rate) == (
        Decimal("1.00"),
        Decimal("18098.640"),
        Decimal("10.50"),
    )


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Importe Total: $ 417855,00", "417855.00"),
        ("TOTAL Pesos 41,623.19", "41623.19"),
        ("Importe Total: $ 69,325.0000", "69325.00"),  # 4 decimales que no son centavos
        ("TOTAL u$s 40,79 $ 43.477,66", "43477.66"),
        ("Total cargos del período $27.590,00", "27590.00"),
        ("...se facturará la percepción. TOTAL $ 41.113,99", "41113.99"),
        ("Subtotal: $40449.77\nTotal: $44697", "44697.00"),  # "Subtotal:" no cuenta
    ],
)
def test_extract_total(text, expected):
    assert _extract_total(text.split("\n"), text) == Decimal(expected)


def test_total_from_row_under_column_header_does_not_take_the_subtotal():
    # El encabezado termina en "TOTAL $": con `\s*` después del $ se levantaba el primer
    # importe de la fila de abajo (el subtotal) en lugar del último (el total).
    lines = [
        "SUBTOTAL $ BONIF.$ SUBTOTAL $ IVA 21%$ IVA 10.5$% Imp.Int.$ TOTAL $",
        "18098.64 0.00 18098.64 0.00 1900.36 0.00 20179.99",
    ]
    assert _extract_total(lines, "\n".join(lines)) == Decimal("20179.99")


def test_tributes_are_summed_from_each_suppliers_wording():
    text = "\n".join(
        [
            "Importe Otros Tributos: $ 0,00",
            "PERCEPCION: CAPITAL FEDERAL Neto: 38993.42 Alicuota: 1.00% Importe: 389.93 389.93",
            "Per IIBB CABA 1.00% 628.84",
            "Percep.IIBB CF RG 155/2010 29.261,04 1,00 292,61",
            "Percepción I.V.A. 27.798,00 3,00 833,94",
            "10.095,05",  # el renglón de abajo NO es parte de la percepción
            "Ley 27.430 Impuestos Internos 5,2631% 27.798,00 5,26 1.463,04",
            "IB CABA 1,00% $ 337,00",
            "Perc.IIBB $ 180.99 Perc.IIBB CABA",
            "0.00 Perc.IIBB Sta. Fe",
        ]
    )
    expected = sum(
        map(Decimal, ["389.93", "628.84", "292.61", "833.94", "1463.04", "337.00", "180.99"])
    )
    assert _extract_tributes_total(text) == expected


def test_totals_lines_for_b_uses_iva_contenido_and_reproduces_the_rate():
    text = "Importe Total: $ 417855,00\nIVA Contenido: $ 72520,29"
    (line,) = _totals_lines(text, "B", Decimal("417855.00"), Decimal(0))
    assert line.unit_price == Decimal("345334.71")
    assert line.iva_rate == Decimal("21")


def test_totals_lines_for_c_is_the_total_without_iva():
    (line,) = _totals_lines("x", "C", Decimal("61580.00"), Decimal(0))
    assert (line.unit_price, line.iva_rate) == (Decimal("61580.00"), Decimal(0))


def test_totals_lines_single_rate_is_exact_and_ignores_the_duplicate_copy():
    # El PDF trae el comprobante dos veces (original y duplicado): el IVA no se cuenta doble.
    text = "IVA 10.5%: $ 22003,53\nIVA 10.5%: $ 22003,53"
    (line,) = _totals_lines(text, "A", Decimal("231561.00"), Decimal(0))
    assert line.unit_price == Decimal("209557.47")  # total - IVA, no IVA / 10,5%


def test_totals_lines_infers_rate_only_when_the_net_is_printed():
    printed = "SUBTOTAL 82.533,03 0,00 82.533,03 8.665,97"
    (line,) = _totals_lines(printed, "A", Decimal("92024.33"), Decimal("825.33"))
    assert line.iva_rate == Decimal("10.5")
    # Sin el neto impreso no se adivina una alícuota: no hay líneas.
    assert _totals_lines("sin datos", "A", Decimal("92024.33"), Decimal("825.33")) == []


def _invoice(voucher_type, lines, totals_lines, total, tributes=Decimal(0)):
    return ParsedInvoice(
        voucher_type=voucher_type,
        pos=2,
        number=1,
        date=datetime.date(2025, 3, 5),
        supplier_cuit=None,
        supplier_name=None,
        supplier_condicion_iva=None,
        cae=None,
        lines=lines,
        total=total,
        tributes_total=tributes,
        totals_lines=totals_lines,
    )


def test_lines_gap_is_zero_when_everything_closes_and_shows_the_difference_when_not():
    a_line = ParsedInvoiceLine("x", Decimal(1), Decimal("100"), Decimal("21"))
    assert lines_gap(_invoice("A", [a_line], [], Decimal("121.00"))) == Decimal("0.00")
    # Una B imprime el precio con el IVA adentro; las líneas derivadas de los totales, neto.
    b_gross = ParsedInvoiceLine("x", Decimal(1), Decimal("121"), Decimal("21"))
    assert lines_gap(_invoice("B", [b_gross], [], Decimal("121.00"))) == Decimal("0.00")
    b_net = ParsedInvoiceLine("x", Decimal(1), Decimal("100"), Decimal("21"))
    assert lines_gap(_invoice("B", [], [b_net], Decimal("121.00")), use_totals=True) == Decimal(
        "0.00"
    )
    # Un total que no cierra no da error: da la diferencia.
    assert lines_gap(_invoice("A", [a_line], [], Decimal("130.00"))) == Decimal("-9.00")
    assert lines_gap(_invoice("A", [a_line], [], None)) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Punto de Venta: 00002 Comp. Nro: 00000508", (2, 508)),
        ("Punto de venta: 0011 Nro. Comp:00092030", (11, 92030)),
        ("A\nFACTURA 0016 - 00140744\nCOD 01", (16, 140744)),
        ("Nº: 00017-00001227", (17, 1227)),
        ("Nro. 00005-00032984 ORIGINAL", (5, 32984)),
        ("Nº0004 - 00024960", (4, 24960)),
        # Polytech parte el número en dos renglones y otro patrón levantaba 901-971132
        # (jurisdicción + IIBB): un número de apariencia válida y equivocado.
        (
            "Vidal 3854 - Factura: 0003-\nCiudad de Bs. As. A 00387105\nFactura 901-971132-1",
            (3, 387105),
        ),
        ("Orig A inal Factura\n0003-00019753\n01", (3, 19753)),
    ],
)
def test_pos_and_number_formats(text, expected):
    assert _extract_pos_number(text.split("\n"), text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("A FACTURA\nNº0004 - 00024960", "A"),
        ("A Factura\nOriginal", "A"),
        ("Orig A inal Factura", "A"),
        ("Ciudad de Bs. As. A 00387105\n", None),  # sin "Factura: 0003-" no hay letra segura
    ],
)
def test_voucher_letter_formats(text, expected):
    assert _extract_voucher_type(text.split("\n"), text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("FECHA: May 15, 2025\nInicio de actividad: 19/04/1991", datetime.date(2025, 5, 15)),
        ("A Factura\n21-01-2025\nIVA Responsable", datetime.date(2025, 1, 21)),
        ("TODOVISION S.A.\nFECHA:28/08/25", datetime.date(2025, 8, 28)),
    ],
)
def test_date_formats(text, expected):
    assert _extract_date(text) == expected


def test_air_supplier_is_known_only_for_its_template_and_point_of_sale():
    air = "FACTURA\nA 0047-00233706\nCOD: 1"
    supplier = _known_supplier(air, 47)
    assert supplier is not None and supplier.cuit == "30-57013558-5"
    # Misma plantilla con otro punto de venta: no se le asigna el CUIT de otro proveedor.
    assert _known_supplier(air, 48) is None
    assert _known_supplier("otra plantilla", 47) is None
