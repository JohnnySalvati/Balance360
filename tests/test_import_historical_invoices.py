"""El loader del histórico. La lectura del PDF está monkeypatched: los tests fijan qué
devuelve `parse_invoice_file` y prueban lo que el loader decide con eso, no el parser."""

from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from balance360.enums import ContactType, DocType, InvoiceType, IvaAliquot
from balance360.models.contact import Contact
from balance360.models.invoice import Invoice
from balance360.services.pdf_invoice import ParsedInvoice, ParsedInvoiceLine
from scripts import import_historical_invoices as loader
from tests.factories import make_entity, make_fiscal_identity


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    # Una subcarpeta para que el `attachments/` (que también vive bajo tmp_path) no caiga
    # dentro del recorrido de `rglob` y termine reingresando el PDF que acabo de guardar.
    d = tmp_path / "source"
    d.mkdir()
    return d


def make_pdf(base_dir: Path, name: str, content: bytes = b"%PDF-1.4 fake") -> Path:
    p = base_dir / name
    p.write_bytes(content)
    return p


def make_parsed(
    *,
    voucher_type: str = "A",
    pos: int = 2,
    number: int = 129,
    date_: datetime.date = datetime.date(2025, 3, 15),
    supplier_cuit: str = "20182810674",
    supplier_name: str = "Jose Miguel Salvati",
    cae: str = "86316182057886",
    total: Decimal = Decimal("1210.00"),
    line_unit: Decimal = Decimal("1000.00"),
    line_rate: Decimal = Decimal("21"),
) -> ParsedInvoice:
    """A que cierra al centavo (1000 + 21% = 1210)."""
    return ParsedInvoice(
        voucher_type=voucher_type,
        pos=pos,
        number=number,
        date=date_,
        supplier_cuit=supplier_cuit,
        supplier_name=supplier_name,
        supplier_condicion_iva="INSCRIPTO",
        cae=cae,
        lines=[ParsedInvoiceLine("Ítem", Decimal(1), line_unit, line_rate)],
        total=total,
        tributes_total=Decimal(0),
        totals_lines=[],
    )


@pytest.fixture
def salvati(db):
    return make_fiscal_identity(db, name="Salvati", tax_id="20182810674")


@pytest.fixture
def viola(db):
    return make_fiscal_identity(db, name="Viola", tax_id="27177624441")


@pytest.fixture(autouse=True)
def _patch_settings(tmp_path, monkeypatch):
    from balance360.database import settings as db_settings

    monkeypatch.setattr(db_settings, "attachments_dir", tmp_path / "attachments")


def _patch_parse(monkeypatch, mapping: dict[str, ParsedInvoice]) -> None:
    def fake(name: str, content: bytes) -> ParsedInvoice:
        return mapping[name]

    monkeypatch.setattr(loader, "parse_invoice_file", fake)


def _run(db, base_dir, kind, monkeypatch):
    """Correr el loader contra `db` en modo commit. `db` es la sesión del test — así el
    rollback del fixture lo limpia todo, sin dejar filas cross-test."""

    def fake_session():
        class _Ctx:
            def __enter__(self_inner):
                return db

            def __exit__(self_inner, *args):
                return False

        return _Ctx()

    monkeypatch.setattr(loader, "SessionLocal", fake_session)
    return loader.run(base_dir, kind, commit=True)


# ----------- felices -----------


def test_sale_creates_invoice_lines_and_attachment(db, salvati, viola, base_dir, monkeypatch):
    make_entity(db, name="InSoft")
    pdf = make_pdf(base_dir, "20182810674_001_00002_00000129.pdf", b"%PDF-fake bytes")
    _patch_parse(monkeypatch, {pdf.name: make_parsed()})

    result = _run(db, base_dir, InvoiceType.sale, monkeypatch)

    assert (result.total, result.imported) == (1, 1)
    invoice = db.execute(select(Invoice)).scalar_one()
    assert invoice.voucher_type.value == "A"
    assert (invoice.pos, invoice.number) == (2, 129)
    assert invoice.cae == "86316182057886"
    assert invoice.fiscal_identity_id == salvati.id
    assert invoice.confirmed and invoice.authorized and not invoice.paid
    assert invoice.fulfilled_at == invoice.date
    assert invoice.external_source == "historical-import"
    assert invoice.external_id == loader.external_id_for(base_dir, pdf)
    assert len(invoice.invoice_lines) == 1
    line = invoice.invoice_lines[0]
    assert (line.quantity, line.unit_price, line.iva_aliquot) == (
        1,
        Decimal("1000.00"),
        IvaAliquot.standard,
    )
    assert len(invoice.attachments) == 1
    stored = invoice.attachments[0]
    assert stored.filename == pdf.name
    assert stored.file_size == pdf.stat().st_size
    # El archivo llegó a disco, con el UUID del stored_filename.
    from balance360.database import settings as db_settings

    assert (db_settings.attachments_dir / stored.stored_filename).read_bytes() == pdf.read_bytes()


def test_purchase_leaves_fiscal_identity_null_and_creates_supplier(db, base_dir, monkeypatch):
    make_entity(db, name="InSoft")
    pdf = make_pdf(base_dir, "30500010912_001_00001_00000100.pdf")
    _patch_parse(
        monkeypatch,
        {
            pdf.name: make_parsed(
                supplier_cuit="30500010912",
                supplier_name="Proveedor SA",
            )
        },
    )

    _run(db, base_dir, InvoiceType.purchase, monkeypatch)

    invoice = db.execute(select(Invoice)).scalar_one()
    assert invoice.fiscal_identity_id is None
    contact = db.execute(select(Contact).where(Contact.tax_id == "30500010912")).scalar_one()
    assert contact.name == "Proveedor SA"
    assert contact.contact_type == ContactType.supplier
    assert contact.doc_type == DocType.CUIT
    assert invoice.contact_id == contact.id


def test_reuses_an_existing_contact_by_cuit(db, base_dir, monkeypatch):
    make_entity(db, name="InSoft")
    from tests.factories import make_contact

    already = make_contact(
        db, name="Ya existía", tax_id="30500010912", contact_type=ContactType.both
    )
    pdf = make_pdf(base_dir, "30500010912_001_00001_00000100.pdf")
    _patch_parse(monkeypatch, {pdf.name: make_parsed(supplier_cuit="30500010912")})

    _run(db, base_dir, InvoiceType.purchase, monkeypatch)

    invoice = db.execute(select(Invoice)).scalar_one()
    assert invoice.contact_id == already.id
    # Ninguna ficha nueva, ni cambio en la existente.
    assert (
        db.execute(select(Contact).where(Contact.tax_id == "30500010912")).scalar_one().name
        == "Ya existía"
    )


# ----------- validaciones -----------


def test_sale_whose_pdf_cuit_does_not_match_the_filename_is_skipped(
    db, salvati, viola, base_dir, monkeypatch
):
    make_entity(db, name="InSoft")
    pdf = make_pdf(base_dir, "20182810674_001_00002_00000129.pdf")  # prefijo: Salvati
    _patch_parse(monkeypatch, {pdf.name: make_parsed(supplier_cuit="27177624441")})  # dice Viola

    result = _run(db, base_dir, InvoiceType.sale, monkeypatch)

    assert (result.imported, result.skipped_other) == (0, 1)
    assert db.execute(select(Invoice)).scalar_one_or_none() is None


def test_sale_whose_cuit_is_not_a_known_fiscal_identity_is_skipped(
    db, salvati, base_dir, monkeypatch
):
    make_entity(db, name="InSoft")
    pdf = make_pdf(base_dir, "30999888771_001_00002_00000200.pdf")
    _patch_parse(monkeypatch, {pdf.name: make_parsed(supplier_cuit="30999888771")})

    result = _run(db, base_dir, InvoiceType.sale, monkeypatch)

    assert (result.imported, result.skipped_other) == (0, 1)


def test_unverified_read_is_skipped_and_nothing_is_written(db, salvati, base_dir, monkeypatch):
    make_entity(db, name="InSoft")
    pdf = make_pdf(base_dir, "20182810674_001_00002_00000129.pdf")
    bad = make_parsed(cae=None)  # header incompleto → is_verified es False
    _patch_parse(monkeypatch, {pdf.name: bad})

    result = _run(db, base_dir, InvoiceType.sale, monkeypatch)

    assert (result.imported, result.skipped_unverified) == (0, 1)
    assert db.execute(select(Invoice)).scalar_one_or_none() is None


# ----------- idempotencia y dry-run -----------


def test_second_run_over_the_same_directory_does_not_duplicate(db, salvati, base_dir, monkeypatch):
    make_entity(db, name="InSoft")
    pdf = make_pdf(base_dir, "20182810674_001_00002_00000129.pdf")
    _patch_parse(monkeypatch, {pdf.name: make_parsed()})

    r1 = _run(db, base_dir, InvoiceType.sale, monkeypatch)
    r2 = _run(db, base_dir, InvoiceType.sale, monkeypatch)

    assert r1.imported == 1
    assert (r2.imported, r2.skipped_existing) == (0, 1)
    assert len(db.execute(select(Invoice)).scalars().all()) == 1


def test_dry_run_lists_but_writes_nothing(db, salvati, base_dir, monkeypatch):
    make_entity(db, name="InSoft")
    pdf = make_pdf(base_dir, "20182810674_001_00002_00000129.pdf")
    _patch_parse(monkeypatch, {pdf.name: make_parsed()})

    from balance360.database import settings as db_settings

    def fake_session():
        class _Ctx:
            def __enter__(self_inner):
                return db

            def __exit__(self_inner, *args):
                return False

        return _Ctx()

    monkeypatch.setattr(loader, "SessionLocal", fake_session)
    result = loader.run(base_dir, InvoiceType.sale, commit=False)

    assert result.imported == 1  # el contador cuenta lo que se HABRÍA importado
    assert db.execute(select(Invoice)).scalar_one_or_none() is None
    assert not (db_settings.attachments_dir).exists() or not any(
        db_settings.attachments_dir.iterdir()
    )


# ----------- helpers puros -----------


def test_external_id_is_stable_by_relative_path(tmp_path):
    a = tmp_path / "sub" / "one.pdf"
    a.parent.mkdir()
    a.write_bytes(b"")
    b = tmp_path / "sub" / "two.pdf"
    b.write_bytes(b"")
    assert loader.external_id_for(tmp_path, a) != loader.external_id_for(tmp_path, b)
    assert loader.external_id_for(tmp_path, a) == loader.external_id_for(tmp_path, a)
    # Independiente del padre: si tomo la misma jerarquía en otra carpeta, los UUID no
    # cambian (el path relativo es el mismo).
    other_root = tmp_path / "clone"
    other_root.mkdir()
    other_a = other_root / "sub" / "one.pdf"
    other_a.parent.mkdir()
    other_a.write_bytes(b"")
    assert loader.external_id_for(tmp_path, a) == loader.external_id_for(other_root, other_a)


def test_to_int_quantity_keeps_integer_and_collapses_fractional_to_amount():
    integer = ParsedInvoiceLine("Cable", Decimal(3), Decimal("1000.00"), Decimal("21"))
    assert loader.to_int_quantity(integer) == (3, Decimal("1000.00"), "Cable")
    frac = ParsedInvoiceLine("Consultoría", Decimal("1.5"), Decimal("8000.00"), Decimal("21"))
    q, unit, desc = loader.to_int_quantity(frac)
    assert (q, unit) == (1, Decimal("12000.0000"))
    assert "1.5" in desc and "8000.00" in desc


def test_aliquot_from_rate_maps_the_four_known_rates():

    assert loader.aliquot_from_rate(Decimal("0")) == IvaAliquot.exempt
    assert loader.aliquot_from_rate(Decimal("10.5")) == IvaAliquot.reduced
    assert loader.aliquot_from_rate(Decimal("21")) == IvaAliquot.standard
    assert loader.aliquot_from_rate(Decimal("27")) == IvaAliquot.higher
    # Un valor desconocido no revienta ni inventa: cae a exempt para que el operador lo
    # corrija después. Un ítem con alícuota rara igual habría bloqueado is_verified.
    assert loader.aliquot_from_rate(Decimal("15")) == IvaAliquot.exempt
