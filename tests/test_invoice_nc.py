from datetime import date
from decimal import Decimal

import pytest

from balance360.enums import InvoiceType, IvaAliquot, VoucherType
from balance360.exceptions import InvoiceRequestError
from balance360.services.invoice import _build_invoice_request
from tests import factories

EMITTER_CUIT = "30500010012"


def _fake_ticket(monkeypatch):
    # _build_invoice_request calls get_access_ticket("wsfe"); keep it off the network.
    monkeypatch.setattr(
        "balance360.services.invoice.get_access_ticket",
        lambda service: {"token": "tok", "sign": "sig"},
    )


def _make_sale(db, fiscal_identity, entity_id, voucher_type, related=None, pos=5, number=None):
    invoice = factories.make_invoice(
        db, invoice_type=InvoiceType.sale, entity_id=entity_id, fiscal_identity=fiscal_identity
    )
    invoice.voucher_type = voucher_type
    invoice.pos = pos
    invoice.number = number
    invoice.date = date(2026, 7, 20)
    invoice.related_invoice = related
    db.commit()
    factories.make_invoice_line(
        db, invoice.id, quantity=1, unit_price=Decimal("100"), iva_aliquot=IvaAliquot.standard
    )
    return invoice


def test_nc_request_includes_associated_voucher(db, monkeypatch):
    _fake_ticket(monkeypatch)
    entity = factories.make_entity(db)
    emitter = factories.make_fiscal_identity(db, entity_id=entity.id, tax_id=EMITTER_CUIT)

    original = _make_sale(db, emitter, entity.id, VoucherType.B, number=1)
    nc = _make_sale(db, emitter, entity.id, VoucherType.NCB, related=original)

    request = _build_invoice_request(nc)
    associated = request.voucher_data.associated_vouchers

    assert len(associated) == 1
    assert associated[0].tipo == 6  # voucher_type_code[VoucherType.B]
    assert associated[0].pos == 5
    assert associated[0].number == 1
    assert associated[0].cuit == int(EMITTER_CUIT)
    assert associated[0].date == date(2026, 7, 20)


def test_plain_invoice_has_no_associated_vouchers(db, monkeypatch):
    _fake_ticket(monkeypatch)
    entity = factories.make_entity(db)
    emitter = factories.make_fiscal_identity(db, entity_id=entity.id, tax_id=EMITTER_CUIT)

    invoice = _make_sale(db, emitter, entity.id, VoucherType.B, number=1)

    request = _build_invoice_request(invoice)
    assert request.voucher_data.associated_vouchers == []


def test_nc_without_related_invoice_raises(db, monkeypatch):
    _fake_ticket(monkeypatch)
    entity = factories.make_entity(db)
    emitter = factories.make_fiscal_identity(db, entity_id=entity.id, tax_id=EMITTER_CUIT)

    nc = _make_sale(db, emitter, entity.id, VoucherType.NCB)

    with pytest.raises(InvoiceRequestError):
        _build_invoice_request(nc)


def test_nc_letter_mismatch_raises(db, monkeypatch):
    _fake_ticket(monkeypatch)
    entity = factories.make_entity(db)
    emitter = factories.make_fiscal_identity(db, entity_id=entity.id, tax_id=EMITTER_CUIT)

    original = _make_sale(db, emitter, entity.id, VoucherType.A, number=1)
    nc = _make_sale(db, emitter, entity.id, VoucherType.NCB, related=original)

    with pytest.raises(InvoiceRequestError):
        _build_invoice_request(nc)
