from datetime import datetime, timedelta, timezone
from decimal import Decimal

from balance360.database import settings
from balance360.enums import CondicionIva, ContactType, DocType, IvaAliquot
from balance360.models.money import money
from balance360.schemas.contact import ContactCreate
from balance360.schemas.entity import EntityCreate
from balance360.services.arca import TicketManager
from balance360.services.text import digits_only, format_cuit
from tests import factories


def test_digits_only():
    assert digits_only("30-50321810-7") == "30503218107"
    assert digits_only("182810674") == "182810674"
    assert digits_only(None) == ""


def test_format_cuit():
    assert format_cuit("30503218107") == "30-50321810-7"
    assert format_cuit("30-50321810-7") == "30-50321810-7"
    assert format_cuit("18281067") == "18281067"
    assert format_cuit("") == ""
    assert format_cuit(None) == ""


def test_money():
    assert money(Decimal("10024.88655")) == Decimal("10024.89")
    assert money(Decimal("1024.55")) == Decimal("1024.55")
    assert money(Decimal(".001")) == Decimal("0.0")


def test_contact_create():
    contact = ContactCreate(
        name="test",
        tax_id="30-50321810-7",
        contact_type=ContactType.both,
        condicion_iva=CondicionIva.INSCRIPTO,
        doc_type=DocType.CUIT,
    )
    assert contact.tax_id == "30503218107"

    contact = ContactCreate(
        name="test",
        tax_id=None,
        contact_type=ContactType.both,
        condicion_iva=CondicionIva.INSCRIPTO,
        doc_type=DocType.CUIT,
    )
    assert contact.tax_id is None


def test_ticket_env_isolation(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(settings, "afip_env", "homo")
    ticket_manager = TicketManager()
    homo_ticket = ticket_manager.save_new_ticket(
        service="wsfe",
        token="token123",
        sign="sign123",
        expiration_time=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )

    monkeypatch.setattr(settings, "afip_env", "prod")
    ticket_manager = TicketManager()

    prod_ticket = ticket_manager.get_valid_ticket("wsfe")
    assert prod_ticket is None

    monkeypatch.setattr(settings, "afip_env", "homo")
    ticket_manager = TicketManager()

    homo_ticket = ticket_manager.get_valid_ticket("wsfe")
    assert homo_ticket is not None


def test_iva_breakdown(db):
    invoice = factories.make_invoice(db)
    factories.make_invoice_line(
        db, invoice_id=invoice.id, unit_price=Decimal("125.55"), iva_aliquot=IvaAliquot.standard
    )
    assert next(
        (
            aliq_line.iva_amount
            for aliq_line in invoice.iva_breakdown
            if aliq_line.aliquot == IvaAliquot.standard
        ),
        None,
    ) == Decimal("26.37")
