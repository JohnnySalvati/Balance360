from decimal import Decimal

import pytest

from balance360.enums import InvoiceType, IvaAliquot, VoucherType
from tests import factories


def _sale_invoice(db, voucher_type):
    invoice = factories.make_invoice(db, invoice_type=InvoiceType.sale)
    invoice.voucher_type = voucher_type
    db.commit()
    return invoice


def test_gross_unit_price_applies_rate_as_percentage(db):
    line = factories.make_invoice_line(
        db, quantity=1, unit_price=Decimal("100"), iva_aliquot=IvaAliquot.standard
    )
    assert line.gross_unit_price == Decimal("121.00")


def test_gross_amount_rounds_unit_first(db):
    # unit-first: money(10.02 * 1.21) = 12.12, then * 7 = 84.84.
    # net-first would be money(70.14 * 1.21) = 84.87 -- this asserts we do NOT do that.
    line = factories.make_invoice_line(
        db, quantity=7, unit_price=Decimal("10.02"), iva_aliquot=IvaAliquot.standard
    )
    assert line.gross_unit_price == Decimal("12.12")
    assert line.gross_amount == Decimal("84.84")
    # the printed identity cantidad x precio = subtotal always holds
    assert line.gross_amount == line.gross_unit_price * line.quantity


def test_bc_invoice_reconciles_gross_first(db):
    invoice = _sale_invoice(db, VoucherType.B)
    factories.make_invoice_line(
        db, invoice.id, quantity=7, unit_price=Decimal("10.02"), iva_aliquot=IvaAliquot.standard
    )

    [breakdown] = invoice.iva_breakdown
    assert breakdown.net_amount == Decimal("70.12")
    assert breakdown.iva_amount == Decimal("14.72")
    assert invoice.net_total == Decimal("70.12")
    assert invoice.total == Decimal("84.84")
    # net + iva == gross keeps AFIP's ImpNeto + ImpIVA == ImpTotal
    assert invoice.net_total + breakdown.iva_amount == invoice.total
    # footer total equals the sum of the printed line subtotals
    assert sum(line.gross_amount for line in invoice.invoice_lines) == invoice.total


def test_a_invoice_stays_net_first(db):
    invoice = _sale_invoice(db, VoucherType.A)
    factories.make_invoice_line(
        db, invoice.id, quantity=7, unit_price=Decimal("10.02"), iva_aliquot=IvaAliquot.standard
    )

    [breakdown] = invoice.iva_breakdown
    assert breakdown.net_amount == Decimal("70.14")
    assert breakdown.iva_amount == Decimal("14.73")
    assert invoice.total == Decimal("84.87")


@pytest.mark.parametrize(
    "voucher_type, expected",
    [
        (VoucherType.A, True),
        (VoucherType.NCA, True),
        (VoucherType.B, False),
        (VoucherType.NCB, False),
        (VoucherType.C, False),
        (VoucherType.NCC, False),
    ],
)
def test_discriminates_iva(db, voucher_type, expected):
    invoice = _sale_invoice(db, voucher_type)
    assert invoice.discriminates_iva is expected
