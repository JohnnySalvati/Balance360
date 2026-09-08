"""Facturar antes de tener la mercadería: el hecho fiscal separado del físico.

El caso que motiva todo esto: se factura una venta para anticipar el cobro de algo que
todavía no llegó. Antes eso era imposible porque confirmar exigía un serial por unidad,
y el serial no existe hasta que la unidad está. Ahora confirmar solo valida el
comprobante, y el serial —con el stock— es requisito de `fulfill_invoice`.

Los tests van por el circuito completo, en el orden real: compra sin recibir, venta
emitida contra esa compra, y recién después las dos entregas.
"""

from decimal import Decimal

import pytest

from balance360.crud import invoice as invoice_crud
from balance360.enums import InvoiceType, IvaAliquot, SerialStatus, VoucherType
from balance360.exceptions import (
    InvoiceConfirmationError,
    InvoiceFulfillmentError,
    SerialValidationError,
)
from balance360.services.invoice import (
    confirm_invoice,
    create_credit_note,
    fulfill_invoice,
    fulfillment_error,
    unconfirm_invoice,
)
from balance360.services.serial_number import add_serial_to_line
from balance360.services.stock import get_product_stock, get_stock_summary
from tests import factories


def _fulfill(db, invoice):
    """Registrar el movimiento con la fecha del comprobante, como hace la pantalla."""
    fulfill_invoice(db, invoice, invoice.date)


def _scene(db):
    """Entidad, identidad fiscal y producto compartidos por todos los comprobantes.

    La identidad se crea una sola vez porque su nombre es unico: dejar que cada
    `make_invoice` arme la suya choca contra el indice al segundo comprobante.
    """
    return (
        factories.make_entity(db),
        factories.make_fiscal_identity(db),
        factories.make_product(db, name="Notebook Lenovo V15", track_serial=True),
    )


def _serial_product_purchase(db, quantity=1):
    """Compra formal de un producto con seriales, sin confirmar y sin seriales cargados."""
    entity, identity, product = _scene(db)
    invoice = factories.make_invoice(
        db,
        invoice_type=InvoiceType.purchase,
        entity_id=entity.id,
        fiscal_identity_id=identity.id,
        voucher_type=VoucherType.A,
        pos=1,
        number=1001,
    )
    line = factories.make_invoice_line(
        db,
        invoice.id,
        product_id=product.id,
        quantity=quantity,
        unit_price=Decimal("800000"),
        iva_aliquot=IvaAliquot.reduced,
    )
    return entity, identity, product, invoice, line


def _sale_of(db, entity, identity, product, quantity=1, formal=False):
    """Venta del mismo producto, sin seriales asignados."""
    invoice = factories.make_invoice(
        db,
        invoice_type=InvoiceType.sale,
        entity_id=entity.id,
        fiscal_identity_id=identity.id,
        formal=formal,
    )
    if not formal:
        invoice.voucher_type = None
    line = factories.make_invoice_line(
        db, invoice.id, product_id=product.id, quantity=quantity, unit_price=Decimal("1100000")
    )
    db.commit()
    return invoice, line


def test_purchase_confirms_without_serials_and_stays_pending(db):
    """La factura del proveedor llegó antes que la mercadería: se confirma igual.

    Es el primer eslabón del bloqueo viejo. El crédito fiscal es del mes de la factura,
    exista o no la unidad, y confirmar es lo que lo registra.
    """
    *_, invoice, _ = _serial_product_purchase(db)

    confirm_invoice(db, invoice)

    assert invoice.confirmed
    assert not invoice.fulfilled
    assert "Faltan 1 de 1 seriales" in (fulfillment_error(db, invoice) or "")


def test_receiving_the_purchase_makes_its_serials_available(db):
    """Los seriales se cargan después de confirmar, y recién ahí entran al stock."""
    entity, _, product, invoice, line = _serial_product_purchase(db)
    confirm_invoice(db, invoice)

    assert get_product_stock(db, product.id, entity.id) == 0

    serial = add_serial_to_line(db, "LNV-0001", line)
    assert serial.status == SerialStatus.pending
    assert fulfillment_error(db, invoice) is None

    _fulfill(db, invoice)

    db.refresh(serial)
    assert invoice.fulfilled
    assert serial.status == SerialStatus.available
    assert get_product_stock(db, product.id, entity.id) == 1


def test_sale_is_issued_before_the_product_exists(db):
    """El caso completo: vender y cobrar lo que todavía no se recibió.

    La venta se confirma sin seriales —no hay de dónde sacarlos— y queda entregable
    pendiente. Que quede confirmada es lo único que hace falta para autorizarla en
    ARCA y mandarle el comprobante al cliente.
    """
    entity, identity, product, purchase, purchase_line = _serial_product_purchase(db)
    confirm_invoice(db, purchase)

    sale, sale_line = _sale_of(db, entity, identity, product)
    confirm_invoice(db, sale)

    assert sale.confirmed
    assert not sale.fulfilled
    # Ni la compra ni la venta movieron una sola unidad todavía.
    assert get_product_stock(db, product.id, entity.id) == 0

    # Llega la mercadería: se carga el serial en la compra y se registra la recepción.
    add_serial_to_line(db, "LNV-0002", purchase_line)
    _fulfill(db, purchase)
    assert get_product_stock(db, product.id, entity.id) == 1

    # Recién ahora la unidad se puede asignar a la venta y entregar.
    serial = add_serial_to_line(db, "LNV-0002", sale_line)
    assert serial.status == SerialStatus.reserved

    _fulfill(db, sale)

    db.refresh(serial)
    assert sale.fulfilled
    assert serial.status == SerialStatus.sold
    assert get_product_stock(db, product.id, entity.id) == 0


def test_sale_without_stock_confirms_but_cannot_be_delivered(db):
    """Un producto sin seriales tampoco bloquea la emisión, solo la entrega.

    Antes `_validate_lines` rechazaba la confirmación por falta de stock, así que
    facturar por adelantado estaba cerrado también por este lado.
    """
    entity, identity, _ = _scene(db)
    product = factories.make_product(db, name="Cable HDMI 2m", track_serial=False)
    sale, _ = _sale_of(db, entity, identity, product, quantity=3)

    confirm_invoice(db, sale)

    assert sale.confirmed
    assert not sale.fulfilled
    assert fulfillment_error(db, sale) == "Stock insuficiente de Cable HDMI 2m"

    with pytest.raises(InvoiceFulfillmentError, match="Stock insuficiente"):
        _fulfill(db, sale)


def test_stock_summary_separates_physical_from_committed(db):
    """Lo comprado sin recibir y lo vendido sin entregar no son stock, son compromisos."""
    entity, identity, product, purchase, purchase_line = _serial_product_purchase(db, quantity=2)
    confirm_invoice(db, purchase)

    add_serial_to_line(db, "LNV-0003", purchase_line)
    add_serial_to_line(db, "LNV-0004", purchase_line)
    _fulfill(db, purchase)

    other = factories.make_invoice(
        db,
        invoice_type=InvoiceType.purchase,
        entity_id=entity.id,
        fiscal_identity_id=identity.id,
        voucher_type=VoucherType.A,
        pos=1,
        number=1002,
    )
    factories.make_invoice_line(
        db, other.id, product_id=product.id, quantity=5, unit_price=Decimal("790000")
    )
    confirm_invoice(db, other)  # sin seriales: queda por recibir

    sale, _ = _sale_of(db, entity, identity, product)
    confirm_invoice(db, sale)  # sin seriales: queda por entregar

    (item,) = [row for row in get_stock_summary(db, entity.id) if row.id == product.id]

    assert item.stock_qty == 2
    assert item.pending_in == 5
    assert item.pending_out == 1
    assert item.available_qty == 1


def test_pending_list_drops_what_a_credit_note_annuls(db):
    """La venta anticipada que se cae deja de estar pendiente y suelta sus reservas."""
    entity, identity, product, purchase, purchase_line = _serial_product_purchase(db)
    confirm_invoice(db, purchase)
    add_serial_to_line(db, "LNV-0005", purchase_line)
    _fulfill(db, purchase)

    sale, sale_line = _sale_of(db, entity, identity, product, formal=True)
    sale.voucher_type = VoucherType.A
    db.commit()
    confirm_invoice(db, sale)
    serial = add_serial_to_line(db, "LNV-0005", sale_line)
    assert serial.status == SerialStatus.reserved

    # Con CAE y sin entregar: exactamente el estado que este cambio hace posible, y el
    # unico desde el que una venta admite NC.
    sale.authorized = True
    sale.cae = "75123456789012"
    db.commit()

    assert sale in invoice_crud.get_pending_fulfillment(db)

    # El cliente se arrepiente antes de la entrega: NC sobre una venta que nunca se movió.
    nc = create_credit_note(db, sale)
    confirm_invoice(db, nc)

    db.refresh(serial)
    assert serial.status == SerialStatus.available
    assert serial.sale_line_id is None
    assert sale not in invoice_crud.get_pending_fulfillment(db)
    assert get_product_stock(db, product.id, entity.id) == 1


def test_fulfilled_invoice_freezes_its_serials(db):
    """Después de registrar el movimiento los seriales no se tocan más."""
    *_, invoice, line = _serial_product_purchase(db)
    confirm_invoice(db, invoice)
    add_serial_to_line(db, "LNV-0006", line)
    _fulfill(db, invoice)

    with pytest.raises(SerialValidationError, match="movimiento de stock"):
        add_serial_to_line(db, "LNV-0007", line)


def test_unconfirming_requires_reverting_the_movement_first(db):
    """Des-confirmar por arriba dejaría el stock movido y el comprobante en borrador."""
    *_, invoice, line = _serial_product_purchase(db)
    confirm_invoice(db, invoice)
    add_serial_to_line(db, "LNV-0008", line)
    _fulfill(db, invoice)

    with pytest.raises(InvoiceConfirmationError, match="revertir"):
        unconfirm_invoice(db, invoice)


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from balance360.dependencies import get_current_user, get_db
    from balance360.main import app

    user = factories.make_user(db)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_pending_sale_offers_the_delivery_action(client, db):
    """La pantalla del comprobante tiene que decir que falta entregar, y dejar hacerlo."""
    entity, identity, product, purchase, purchase_line = _serial_product_purchase(db)
    confirm_invoice(db, purchase)
    add_serial_to_line(db, "LNV-0009", purchase_line)
    _fulfill(db, purchase)

    sale, sale_line = _sale_of(db, entity, identity, product)
    confirm_invoice(db, sale)

    html = client.get(f"/invoices/{sale.id}").text
    assert "Entrega pendiente" in html
    assert f'hx-post="/invoices/{sale.id}/fulfill"' in html

    pending = client.get("/stock/pending").text
    assert "Faltan 1 de 1 seriales" in pending

    stock = client.get("/stock/").text
    assert "Comprometido" in stock

    add_serial_to_line(db, "LNV-0009", sale_line)
    response = client.post(
        f"/invoices/{sale.id}/fulfill", data={"fulfilled_at": sale.date.isoformat()}
    )

    assert response.status_code == 200
    db.refresh(sale)
    assert sale.fulfilled
    assert client.get("/stock/pending").text.count("Entrega pendiente") == 0
