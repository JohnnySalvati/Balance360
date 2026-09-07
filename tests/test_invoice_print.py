"""Impresión de comprobantes: el fiscal con el layout de ARCA, el informal aparte.

Un informal es un documento interno sin validez fiscal y no tiene que poder
confundirse con una factura: se prueba que se imprime y que su HTML no lleva
nada del papel de ARCA (CAE, QR, "Comprobante Autorizado").
"""

import datetime
import uuid
from decimal import Decimal
from types import SimpleNamespace

from balance360.enums import InvoiceType, VoucherType
from balance360.services.invoice_pdf import pdf_filename
from balance360.web.invoices import _invoice_pdf_html
from tests import factories


def _informal_sale(db, *, confirmed: bool):
    invoice = factories.make_invoice(
        db, invoice_type=InvoiceType.sale, formal=False, voucher_type=None
    )
    invoice.voucher_type = None
    invoice.confirmed = confirmed
    factories.make_invoice_line(
        db, invoice.id, description="Honorarios", quantity=1, unit_price=Decimal("150000")
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def test_informal_confirmado_es_imprimible_pero_no_es_documento_fiscal(db):
    invoice = _informal_sale(db, confirmed=True)

    assert invoice.is_printable
    assert not invoice.is_fiscal_document


def test_informal_borrador_no_es_imprimible(db):
    invoice = _informal_sale(db, confirmed=False)

    assert not invoice.is_printable


def test_el_pdf_informal_no_parece_una_factura(db):
    invoice = _informal_sale(db, confirmed=True)

    html = _invoice_pdf_html(invoice)

    assert "SIN VALIDEZ FISCAL" in html
    assert "NO FISCAL" in html
    # Nada del comprobante fiscal de ARCA.
    for marca_fiscal in ("CAE", "Comprobante Autorizado", "ORIGINAL", "www.arca.gob.ar"):
        assert marca_fiscal not in html
    # El total sí está.
    assert "150.000" in html


def test_pdf_filename_informal_usa_fecha_y_id():
    invoice = SimpleNamespace(
        voucher_type=None,
        pos=None,
        number=None,
        invoice_type=InvoiceType.sale,
        date=datetime.date(2026, 9, 7),
        id=uuid.UUID("6f6a1e4e-5b2a-45d3-9bdb-a46f894da179"),
    )
    assert pdf_filename(invoice) == "comprobante-venta-20260907-6f6a1e4e.pdf"


def test_pdf_filename_informal_sin_numero_aunque_tenga_letra():
    """Un borrador formal pasado a informal puede conservar la letra pero no el número."""
    invoice = SimpleNamespace(
        voucher_type=VoucherType.A,
        pos=None,
        number=None,
        invoice_type=InvoiceType.purchase,
        date=datetime.date(2026, 9, 7),
        id=uuid.UUID("6f6a1e4e-5b2a-45d3-9bdb-a46f894da179"),
    )
    assert pdf_filename(invoice) == "comprobante-compra-20260907-6f6a1e4e.pdf"
