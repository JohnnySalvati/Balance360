import datetime
from decimal import Decimal

import pytest

from balance360.enums import InvoiceType, TributeType, VoucherType
from balance360.models.invoice_tribute import InvoiceTribute
from balance360.reports import (
    MAX_EVOLUTION_MONTHS,
    get_monthly_evolution,
    get_monthly_income_expense,
    get_monthly_profit,
)
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


# --- Reporte de evolución -----------------------------------------------------


def test_la_evolucion_cubre_todo_el_periodo_aunque_falten_meses(db, escenario):
    entity, fiscal_identity = escenario

    _sale(db, entity, fiscal_identity, datetime.date(2026, 3, 10), Decimal("1000"))

    evolution = get_monthly_evolution(db, datetime.date(2026, 1, 1), datetime.date(2026, 6, 30))

    assert [m["label"] for m in evolution["months"]] == [
        "Ene 2026",
        "Feb 2026",
        "Mar 2026",
        "Abr 2026",
        "May 2026",
        "Jun 2026",
    ]
    assert evolution["months"][2]["net_sales"] == Decimal("1000")
    assert evolution["months"][0]["net_sales"] == 0


def test_separa_ventas_de_compras(db, escenario):
    entity, fiscal_identity = escenario
    dia = datetime.date(2026, 3, 10)

    _sale(db, entity, fiscal_identity, dia, Decimal("1000"))
    _purchase(db, entity, fiscal_identity, dia, Decimal("400"))

    evolution = get_monthly_evolution(db, datetime.date(2026, 3, 1), datetime.date(2026, 3, 31))
    marzo = evolution["months"][0]

    assert marzo["net_sales"] == Decimal("1000")
    assert marzo["net_purchases"] == Decimal("400")
    assert marzo["margin"] == Decimal("600")
    assert marzo["net_profit"] == Decimal("600")


def test_los_totales_son_la_suma_de_los_meses(db, escenario):
    entity, fiscal_identity = escenario

    _sale(db, entity, fiscal_identity, datetime.date(2026, 1, 10), Decimal("1000"))
    _sale(db, entity, fiscal_identity, datetime.date(2026, 2, 10), Decimal("500"))
    _purchase(db, entity, fiscal_identity, datetime.date(2026, 2, 10), Decimal("200"))

    evolution = get_monthly_evolution(db, datetime.date(2026, 1, 1), datetime.date(2026, 3, 31))

    assert evolution["totals"]["net_sales"] == Decimal("1500")
    assert evolution["totals"]["net_purchases"] == Decimal("200")
    assert evolution["totals"]["net_profit"] == Decimal("1300")


def test_un_periodo_gigante_se_recorta(db, escenario):
    """ "Todos los años" en el filtro resuelve a 1900-01-01: serían mil columnas."""
    evolution = get_monthly_evolution(db, datetime.date(1900, 1, 1), datetime.date(2026, 8, 31))

    assert evolution["truncated"] is True
    assert len(evolution["months"]) == MAX_EVOLUTION_MONTHS
    assert evolution["months"][-1]["label"] == "Ago 2026"


def test_un_periodo_normal_no_se_recorta(db, escenario):
    evolution = get_monthly_evolution(db, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))

    assert evolution["truncated"] is False
    assert len(evolution["months"]) == 12


def test_la_ganancia_del_reporte_coincide_con_la_del_dashboard(db, escenario):
    """Las dos vistas tienen que dar el mismo número para el mismo mes."""
    entity, fiscal_identity = escenario
    hoy = datetime.date.today()

    _sale(db, entity, fiscal_identity, hoy, Decimal("1000"))
    _purchase(db, entity, fiscal_identity, hoy, Decimal("400"))

    del_dashboard = get_monthly_profit(db, months=12)
    del_reporte = get_monthly_evolution(db, hoy.replace(day=1), hoy)

    assert del_dashboard[-1] == del_reporte["months"][-1]["net_profit"]
