"""Ciclo de vida de los seriales al confirmar y des-confirmar.

Cubre el arreglo de unconfirm_invoice: una NC de compra confirmada deja los
seriales en Devuelto, y des-confirmarla los tiene que devolver a Disponible.
"""

from decimal import Decimal

from balance360.crud import invoice_line as invoice_line_crud
from balance360.enums import InvoiceType, IvaAliquot, SerialStatus, VoucherType
from balance360.services.invoice import (
    confirm_invoice,
    create_credit_note,
    delete_invoice_line,
    unconfirm_invoice,
)
from balance360.web import invoices as invoice_routes
from tests import factories

SERIALS = ("HKS-DDR3-0001", "HKS-DDR3-0002")


def _make_purchase_with_serials(db):
    """Compra A 1-88770 a VENEX por 2 SODIMM DDR3 4GB HIKSEMI, sin confirmar."""
    entity = factories.make_entity(db)
    contact = factories.make_contact(db, name="VENEX")
    product = factories.make_product(db, name="SODIMM DDR3 4GB HIKSEMI", track_serial=True)

    invoice = factories.make_invoice(
        db,
        invoice_type=InvoiceType.purchase,
        entity_id=entity.id,
        contact_id=contact.id,
        voucher_type=VoucherType.A,
        pos=1,
        number=88770,
    )
    line = factories.make_invoice_line(
        db,
        invoice.id,
        product_id=product.id,
        description="SODIMM DDR3 4GB HIKSEMI",
        quantity=2,
        unit_price=Decimal("10000"),
        iva_aliquot=IvaAliquot.standard,
    )
    serials = [factories.make_serial_number(db, serial, product.id, line.id) for serial in SERIALS]
    return invoice, serials


def _statuses(db, serials):
    for serial in serials:
        db.refresh(serial)
    return [serial.status for serial in serials]


def test_purchase_confirmation_makes_serials_available(db):
    invoice, serials = _make_purchase_with_serials(db)

    assert _statuses(db, serials) == [SerialStatus.pending] * 2

    confirm_invoice(db, invoice)

    assert invoice.confirmed
    assert _statuses(db, serials) == [SerialStatus.available] * 2


def test_purchase_nc_cycle_returns_and_restores_serials(db):
    invoice, serials = _make_purchase_with_serials(db)
    confirm_invoice(db, invoice)

    nc = create_credit_note(db, invoice)
    # En una compra el numero de la NC viene impreso en el comprobante del proveedor.
    nc.number = 88771
    db.commit()

    assert nc.voucher_type == VoucherType.NCA
    assert nc.related_invoice == invoice

    confirm_invoice(db, nc)

    assert nc.confirmed
    assert _statuses(db, serials) == [SerialStatus.returned] * 2

    unconfirm_invoice(db, nc)

    assert not nc.confirmed
    assert _statuses(db, serials) == [SerialStatus.available] * 2


def test_nc_without_related_invoice_confirms_without_touching_serials(db):
    """Una NC cargada a mano desde el portal de ARCA no tiene comprobante original."""
    invoice, serials = _make_purchase_with_serials(db)
    confirm_invoice(db, invoice)

    loose_nc = factories.make_invoice(
        db,
        invoice_type=InvoiceType.purchase,
        entity_id=invoice.entity_id,
        contact_id=invoice.contact_id,
        fiscal_identity_id=invoice.fiscal_identity_id,
        voucher_type=VoucherType.NCA,
        pos=1,
        number=99999,
    )
    factories.make_invoice_line(db, loose_nc.id, quantity=1, unit_price=Decimal("100"))

    assert loose_nc.related_invoice is None

    confirm_invoice(db, loose_nc)

    assert loose_nc.confirmed
    assert _statuses(db, serials) == [SerialStatus.available] * 2

    unconfirm_invoice(db, loose_nc)

    assert not loose_nc.confirmed
    assert _statuses(db, serials) == [SerialStatus.available] * 2


def _make_sale_with_reserved_serial(db):
    """Venta informal sin confirmar con un serial reservado a su unica linea."""
    entity = factories.make_entity(db)
    product = factories.make_product(db, name="Gabinete GAMEMAX NOVA N5", track_serial=True)

    purchase = factories.make_invoice(db, invoice_type=InvoiceType.purchase, entity_id=entity.id)
    purchase_line = factories.make_invoice_line(
        db, purchase.id, product_id=product.id, quantity=1, unit_price=Decimal("51000")
    )
    serial = factories.make_serial_number(
        db, "GMX-0001", product.id, purchase_line.id, status=SerialStatus.available
    )

    sale = factories.make_invoice(
        db,
        invoice_type=InvoiceType.sale,
        entity_id=entity.id,
        contact_id=purchase.contact_id,
        fiscal_identity_id=purchase.fiscal_identity_id,
        formal=False,
    )
    sale.voucher_type = None
    sale_line = factories.make_invoice_line(db, sale.id, product_id=product.id, quantity=1)
    serial.sale_line_id = sale_line.id
    serial.status = SerialStatus.reserved
    db.commit()
    return sale, sale_line, serial


def test_deleting_sale_line_releases_its_reserved_serials(db):
    """Borrar la linea tiene que soltar el serial: la FK es SET NULL y el estado
    no se revierte solo, asi que sin esto queda en `reserved` sin venta."""
    sale, sale_line, serial = _make_sale_with_reserved_serial(db)

    delete_invoice_line(db, sale_line)

    db.refresh(serial)
    assert serial.status == SerialStatus.available
    assert serial.sale_line_id is None
    assert invoice_line_crud.get_by_id(db, sale_line.id) is None


def test_scanning_serial_into_informal_sale_creates_exempt_line(db):
    """Un informal no puede tener lineas con IVA: la alicuota de la compra no se
    hereda aunque el escaneo sea el que crea la linea."""
    sale, _, serial = _make_sale_with_reserved_serial(db)
    # Reusar la venta como informal fresca: sacar la linea y el serial de escena.
    db.refresh(sale)
    for line in list(sale.invoice_lines):
        delete_invoice_line(db, line)
    serial.purchase_line.iva_aliquot = IvaAliquot.reduced
    db.commit()

    invoice_routes.scan_serial(request=None, invoice=sale, serial=serial.serial, db=db)

    db.refresh(sale)
    line = sale.invoice_lines[0]
    assert line.iva_aliquot == IvaAliquot.exempt
    assert line.iva_rate == Decimal(0)


def test_scanning_serial_into_formal_sale_inherits_purchase_aliquot(db):
    """En un comprobante formal la alicuota si se hereda de la compra: su IVA es
    lo que despues se declara."""
    sale, _, serial = _make_sale_with_reserved_serial(db)
    db.refresh(sale)
    for line in list(sale.invoice_lines):
        delete_invoice_line(db, line)
    sale.formal = True
    sale.voucher_type = VoucherType.A
    serial.purchase_line.iva_aliquot = IvaAliquot.reduced
    db.commit()

    invoice_routes.scan_serial(request=None, invoice=sale, serial=serial.serial, db=db)

    db.refresh(sale)
    assert sale.invoice_lines[0].iva_aliquot == IvaAliquot.reduced
