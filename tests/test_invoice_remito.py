"""Remito de entrega a partir de una venta.

Lo que importa probar acá es lo que el remito NO tiene: importes. Es un papel que
firma quien recibe la mercadería —muchas veces alguien de depósito— y que no tiene
por qué mostrar lo que se cobró. El resto son las puertas: venta sí, compra no,
borrador no, nota de crédito no.
"""

import datetime
import uuid
from decimal import Decimal
from types import SimpleNamespace

from balance360.enums import InvoiceType, SerialStatus, VoucherType
from balance360.services.invoice_pdf import insoft_logo_data_uri, remito_filename
from balance360.web.invoices import _remito_html
from balance360.web.templating import templates
from tests import factories


def _sale(db, *, confirmed=True, voucher_type=VoucherType.A, **kwargs):
    invoice = factories.make_invoice(
        db, invoice_type=InvoiceType.sale, voucher_type=voucher_type, **kwargs
    )
    invoice.confirmed = confirmed
    factories.make_invoice_line(
        db, invoice.id, description="Notebook Lenovo", quantity=2, unit_price=Decimal("850000")
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def test_venta_confirmada_tiene_remito(db):
    assert _sale(db).has_remito


def test_borrador_no_tiene_remito(db):
    """Las líneas todavía pueden cambiar: un remito impreso sobre un borrador
    puede describir una entrega que después no coincide con la factura."""
    assert not _sale(db, confirmed=False).has_remito


def test_compra_no_tiene_remito(db):
    """El remito lo emite el que entrega. El de una compra lo trae el proveedor."""
    invoice = factories.make_invoice(db, invoice_type=InvoiceType.purchase)
    invoice.confirmed = True
    db.commit()

    assert not invoice.has_remito


def test_nota_de_credito_no_tiene_remito(db):
    """Lo que vuelve lo manda el cliente, con su propio papel."""
    assert not _sale(db, voucher_type=VoucherType.NCA).has_remito


def test_el_remito_no_lleva_ni_un_importe(db):
    invoice = _sale(db)

    html = _remito_html(invoice)

    assert "REMITO" in html
    assert "Notebook Lenovo" in html
    # Ni el unitario, ni el importe de la línea, ni el total, ni el signo.
    assert "850.000" not in html
    assert "1.700.000" not in html
    assert "$" not in html
    # Tampoco nada del papel fiscal.
    for marca_fiscal in ("CAE", "Comprobante Autorizado", "www.arca.gob.ar", "IVA"):
        assert marca_fiscal not in html


def test_el_remito_lleva_cantidades_y_el_logo_de_insoft(db):
    invoice = _sale(db)

    html = _remito_html(invoice)

    assert 'Total de unidades: <span class="n">2</span>' in html
    # El logo embebido, no una URL relativa que weasyprint no resuelve.
    assert insoft_logo_data_uri() in html
    assert "/static/insoft-logo.svg" not in html


def test_el_remito_referencia_el_comprobante_que_lo_origina(db):
    """El remito no tiene numeración propia: se identifica por la factura."""
    invoice = _sale(db, pos=5, number=123)

    html = _remito_html(invoice)

    assert "00005-00000123" in html


def test_el_remito_lista_los_seriales_entregados(db):
    # La entidad y la identidad fiscal se crean una vez y se comparten. `make_invoice`
    # sin `entity_id` / `fiscal_identity_id` crea una de cada una llamada "Test", y los
    # dos nombres son únicos: la compra y la venta de este test chocaban entre sí.
    # Además es lo que corresponde — compramos y vendemos la misma unidad, desde la
    # misma entidad; el resto de los tests usa una sola factura y no lo necesita.
    entity = factories.make_entity(db, name="Remitos")
    fiscal_identity = factories.make_fiscal_identity(db, name="Remitos")
    product = factories.make_product(db, name="Notebook", track_serial=True)
    purchase = factories.make_invoice(
        db,
        invoice_type=InvoiceType.purchase,
        entity_id=entity.id,
        fiscal_identity_id=fiscal_identity.id,
    )
    purchase_line = factories.make_invoice_line(db, purchase.id, product_id=product.id)

    invoice = _sale(db, entity_id=entity.id, fiscal_identity_id=fiscal_identity.id)
    sale_line = factories.make_invoice_line(
        db, invoice.id, product_id=product.id, description=None, quantity=1
    )
    serial = factories.make_serial_number(
        db,
        serial="NB-0001",
        product_id=product.id,
        purchase_line_id=purchase_line.id,
        status=SerialStatus.sold,
    )
    serial.sale_line_id = sale_line.id
    db.commit()
    db.refresh(invoice)

    assert "NB-0001" in _remito_html(invoice)


def _pending_html(db, invoice):
    """La pantalla de pendientes con un solo comprobante, sin bloqueos."""
    return templates.get_template("stock/pending.html").render({"rows": [(invoice, None)]})


def test_la_pantalla_de_pendientes_ofrece_el_remito_de_la_venta(db):
    """Es donde se mira lo que falta entregar, así que es de donde sale el papel."""
    invoice = _sale(db)

    html = _pending_html(db, invoice)

    assert f"/invoices/{invoice.id}/remito" in html
    # Sin esto el click abriría el detalle: la fila entera es un enlace.
    assert "event.stopPropagation()" in html


def test_la_pantalla_de_pendientes_no_ofrece_remito_para_una_compra(db):
    """Lo que falta recibir no se remite: el papel lo trae el proveedor."""
    invoice = factories.make_invoice(db, invoice_type=InvoiceType.purchase)
    invoice.confirmed = True
    db.commit()

    assert "/remito" not in _pending_html(db, invoice)


def test_el_logo_es_un_data_uri_de_svg():
    assert insoft_logo_data_uri().startswith("data:image/svg+xml;base64,")


def test_remito_filename_usa_la_numeracion_del_comprobante():
    invoice = SimpleNamespace(
        pos=5,
        number=123,
        date=datetime.date(2026, 9, 22),
        id=uuid.UUID("6f6a1e4e-5b2a-45d3-9bdb-a46f894da179"),
    )
    assert remito_filename(invoice) == "remito-00005-00000123.pdf"


def test_remito_filename_sin_numeracion_usa_fecha_e_id():
    invoice = SimpleNamespace(
        pos=None,
        number=None,
        date=datetime.date(2026, 9, 22),
        id=uuid.UUID("6f6a1e4e-5b2a-45d3-9bdb-a46f894da179"),
    )
    assert remito_filename(invoice) == "remito-20260922-6f6a1e4e.pdf"
