import datetime
from decimal import Decimal

import pytest

from balance360.enums import InvoiceType, TributeType, VoucherType
from balance360.models.invoice_tribute import InvoiceTribute
from balance360.reports import get_monthly_income_expense, get_monthly_profit
from tests.factories import (
    make_entity,
    make_fiscal_identity,
    make_invoice,
    make_invoice_line,
)


def _sale(db, entity, fiscal_identity, date, unit_price, quantity=1, voucher_type=VoucherType.A):
    invoice = make_invoice(
        db,
        invoice_type=InvoiceType.sale,
        entity_id=entity.id,
        fiscal_identity_id=fiscal_identity.id,
        date=date,
        voucher_type=voucher_type,
    )
    invoice.confirmed = True
    db.commit()
    make_invoice_line(db, invoice_id=invoice.id, quantity=quantity, unit_price=unit_price)
    return invoice


def _purchase(db, entity, fiscal_identity, date, unit_price, quantity=1):
    invoice = make_invoice(
        db,
        invoice_type=InvoiceType.purchase,
        entity_id=entity.id,
        fiscal_identity_id=fiscal_identity.id,
        date=date,
        voucher_type=VoucherType.A,
    )
    invoice.confirmed = True
    db.commit()
    make_invoice_line(db, invoice_id=invoice.id, quantity=quantity, unit_price=unit_price)
    return invoice


@pytest.fixture
def escenario(db):
    entity = make_entity(db, name="InSoft")
    fiscal_identity = make_fiscal_identity(db, name="InSoft SRL")
    return entity, fiscal_identity


def test_la_serie_tiene_un_valor_por_mes(db, escenario):
    """La linea y las barras se aparean por posicion: mismo largo o el grafico miente."""
    perfil = get_monthly_profit(db, months=12)
    barras = get_monthly_income_expense(db, months=12)

    assert len(perfil) == 12
    assert len(perfil) == len(barras)


def test_meses_sin_comprobantes_valen_cero(db, escenario):
    perfil = get_monthly_profit(db, months=12)

    assert all(valor == 0 for valor in perfil)


def test_margen_es_ventas_menos_compras(db, escenario):
    entity, fiscal_identity = escenario
    hoy = datetime.date.today()

    _sale(db, entity, fiscal_identity, hoy, Decimal("1000"))
    _purchase(db, entity, fiscal_identity, hoy, Decimal("400"))

    perfil = get_monthly_profit(db, months=12)

    assert perfil[-1] == Decimal("600")


def test_una_nota_de_credito_resta(db, escenario):
    entity, fiscal_identity = escenario
    hoy = datetime.date.today()

    _sale(db, entity, fiscal_identity, hoy, Decimal("1000"))
    _sale(db, entity, fiscal_identity, hoy, Decimal("250"), voucher_type=VoucherType.NCA)

    perfil = get_monthly_profit(db, months=12)

    assert perfil[-1] == Decimal("750")


def test_cada_comprobante_cae_en_su_mes(db, escenario):
    entity, fiscal_identity = escenario
    hoy = datetime.date.today().replace(day=15)
    mes_anterior = (hoy.replace(day=1) - datetime.timedelta(days=1)).replace(day=15)

    _sale(db, entity, fiscal_identity, hoy, Decimal("1000"))
    _sale(db, entity, fiscal_identity, mes_anterior, Decimal("300"))

    perfil = get_monthly_profit(db, months=12)

    assert perfil[-1] == Decimal("1000")
    assert perfil[-2] == Decimal("300")


def test_los_tributos_restan_una_sola_vez_por_renglon(db, escenario):
    """Con varios renglones y varios tributos, joinear todo junto multiplicaria las filas."""
    entity, fiscal_identity = escenario
    hoy = datetime.date.today()

    invoice = _sale(db, entity, fiscal_identity, hoy, Decimal("1000"))
    make_invoice_line(db, invoice_id=invoice.id, quantity=1, unit_price=Decimal("500"))
    make_invoice_line(db, invoice_id=invoice.id, quantity=1, unit_price=Decimal("500"))

    for _ in range(2):
        db.add(
            InvoiceTribute(
                invoice_id=invoice.id,
                tribute_type=TributeType.municipal,
                description="Tasa",
                base_amount=Decimal("1000"),
                rate=Decimal("10"),
            )
        )
    db.commit()

    perfil = get_monthly_profit(db, months=12)

    # 2000 de ventas menos 2 tributos de 100 cada uno.
    assert perfil[-1] == Decimal("1800")


def test_el_iibb_de_la_identidad_fiscal_resta(db, escenario):
    entity, _ = escenario
    fiscal_identity = make_fiscal_identity(db, name="Con IIBB")
    fiscal_identity.iibb_rate = Decimal("3")
    db.commit()
    hoy = datetime.date.today()

    _sale(db, entity, fiscal_identity, hoy, Decimal("1000"))

    perfil = get_monthly_profit(db, months=12)

    assert perfil[-1] == Decimal("970")


def test_los_comprobantes_sin_confirmar_no_cuentan(db, escenario):
    entity, fiscal_identity = escenario
    hoy = datetime.date.today()

    invoice = make_invoice(
        db,
        invoice_type=InvoiceType.sale,
        entity_id=entity.id,
        fiscal_identity_id=fiscal_identity.id,
        date=hoy,
        voucher_type=VoucherType.A,
    )
    make_invoice_line(db, invoice_id=invoice.id, quantity=1, unit_price=Decimal("1000"))

    perfil = get_monthly_profit(db, months=12)

    assert perfil[-1] == 0


def test_filtra_por_entidad(db, escenario):
    entity, fiscal_identity = escenario
    otra = make_entity(db, name="Familia")
    hoy = datetime.date.today()

    _sale(db, entity, fiscal_identity, hoy, Decimal("1000"))
    _sale(db, otra, fiscal_identity, hoy, Decimal("777"))

    perfil = get_monthly_profit(db, months=12, entity_ids=[entity.id])

    assert perfil[-1] == Decimal("1000")
