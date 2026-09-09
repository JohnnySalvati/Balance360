"""Previsión de gastos: generación de ocurrencias y armado de la grilla mezclada.

Ver `docs/prevision-de-gastos.md` para el porqué de cada decisión que estos tests fijan.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from balance360.crud import recurrence as recurrence_crud
from balance360.crud import transaction as transaction_crud
from balance360.dependencies import Period
from balance360.enums import ClassificationStatus, IntervalUnit, TransactionType
from balance360.services.forecast import ghost_window, occurrences, project
from balance360.web.transactions import TransactionFilters, rows_context
from tests import factories


def _period(start: date, end: date) -> Period:
    return Period(start=start, end=end, year="", month="", date_from="", date_to="")


# --------------------------------------------------------------------------
# El calendario: lo que decide si la serie cae donde tiene que caer
# --------------------------------------------------------------------------


def test_monthly_from_day_31_clamps_february_and_returns_to_31(db):
    """El test central del generador.

    Ancla el 31/01: febrero no tiene 31 y hay que clampear. Lo que importa es lo que pasa
    **después**: marzo tiene que volver al 31. Si las ocurrencias se calcularan incrementando
    la anterior en vez de desde el ancla, la serie quedaría pegada al 28 para siempre.
    """
    recurrence = factories.make_recurrence(db, starts_on=date(2026, 1, 31))

    result = list(occurrences(recurrence, date(2026, 1, 1), date(2026, 6, 30)))

    assert result == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
        date(2026, 5, 31),
        date(2026, 6, 30),
    ]


def test_yearly_from_feb_29_clamps_on_non_leap_years(db):
    recurrence = factories.make_recurrence(
        db, starts_on=date(2024, 2, 29), interval_unit=IntervalUnit.year
    )

    result = list(occurrences(recurrence, date(2024, 1, 1), date(2028, 12, 31)))

    assert result == [
        date(2024, 2, 29),
        date(2025, 2, 28),
        date(2026, 2, 28),
        date(2027, 2, 28),
        date(2028, 2, 29),
    ]


def test_interval_count_greater_than_one(db):
    """Sueldos cada dos semanas: la unidad sola no alcanza, el count es la otra mitad."""
    recurrence = factories.make_recurrence(
        db,
        starts_on=date(2026, 9, 1),
        interval_unit=IntervalUnit.week,
        interval_count=2,
    )

    result = list(occurrences(recurrence, date(2026, 9, 1), date(2026, 10, 15)))

    assert result == [date(2026, 9, 1), date(2026, 9, 15), date(2026, 9, 29), date(2026, 10, 13)]


def test_ends_on_is_inclusive(db):
    recurrence = factories.make_recurrence(
        db, starts_on=date(2026, 1, 10), ends_on=date(2026, 3, 10)
    )

    result = list(occurrences(recurrence, date(2026, 1, 1), date(2026, 12, 31)))

    assert result == [date(2026, 1, 10), date(2026, 2, 10), date(2026, 3, 10)]


def test_window_starting_long_after_anchor_does_not_exhaust_the_safety_cap(db):
    """Una diaria anclada seis años atrás.

    Iterando desde el ancla son más de dos mil pasos: se comería `MAX_OCCURRENCES` y la
    previsión saldría **vacía sin dar error**, que es el peor modo de fallar. El generador
    salta directo al primer paso de la ventana.
    """
    recurrence = factories.make_recurrence(
        db, starts_on=date(2020, 1, 1), interval_unit=IntervalUnit.day
    )

    result = list(occurrences(recurrence, date(2026, 9, 10), date(2026, 9, 13)))

    assert result == [
        date(2026, 9, 10),
        date(2026, 9, 11),
        date(2026, 9, 12),
        date(2026, 9, 13),
    ]


def test_empty_window_yields_nothing(db):
    recurrence = factories.make_recurrence(db, starts_on=date(2026, 1, 1))

    assert list(occurrences(recurrence, date(2026, 6, 1), date(2026, 5, 1))) == []


# --------------------------------------------------------------------------
# La ventana de fantasmas
# --------------------------------------------------------------------------


def test_ghost_window_starts_tomorrow_at_the_earliest():
    start, end = ghost_window(date(2000, 1, 1), date.today() + timedelta(days=30))
    assert start == date.today() + timedelta(days=1)


def test_ghost_window_is_empty_for_a_period_that_ended(db):
    start, end = ghost_window(date(2020, 1, 1), date(2020, 12, 31))
    assert start > end


# --------------------------------------------------------------------------
# project(): filtros y supresión
# --------------------------------------------------------------------------


def test_project_respects_the_account_filter(db):
    # Una sola moneda para las dos cuentas: `make_account` sin `currency_id` crea una moneda
    # nueva y el código "ARS" es único, así que dos altas seguidas chocan.
    currency = factories.make_currency(db)
    banco = factories.make_account(db, name="Banco", currency_id=currency.id)
    caja = factories.make_account(db, name="Caja", currency_id=currency.id)
    factories.make_recurrence(
        db, account_id=banco.id, description="Alquiler", starts_on=date(2026, 1, 5)
    )
    factories.make_recurrence(
        db, account_id=caja.id, description="Kiosco", starts_on=date(2026, 1, 7)
    )

    result = project(db, date(2026, 1, 1), date(2026, 1, 31), account_id=caja.id)

    assert [p.description for p in result] == ["Kiosco"]


def test_project_respects_the_description_filter(db):
    account = factories.make_account(db)
    factories.make_recurrence(
        db, account_id=account.id, description="Alquiler oficina", starts_on=date(2026, 1, 5)
    )
    factories.make_recurrence(
        db, account_id=account.id, description="Internet", starts_on=date(2026, 1, 7)
    )

    result = project(db, date(2026, 1, 1), date(2026, 1, 31), description="alquiler")

    assert [p.description for p in result] == ["Alquiler oficina"]


def test_project_returns_nothing_when_filtering_by_classification_status(db):
    """Un fantasma no está pendiente de clasificar: no existe.

    Ese filtro es sobre trabajo de clasificación, y no hay nada que clasificar en algo que
    todavía no pasó.
    """
    factories.make_recurrence(db, starts_on=date(2026, 1, 1))

    result = project(
        db,
        date(2026, 1, 1),
        date(2026, 12, 31),
        classification_status=ClassificationStatus.unclassified,
    )

    assert result == []


def test_project_skips_paused_recurrences(db):
    factories.make_recurrence(db, starts_on=date(2026, 1, 1), is_active=False)

    assert project(db, date(2026, 1, 1), date(2026, 12, 31)) == []


def test_project_skips_dates_already_taken_by_a_real_transaction(db):
    """Una transacción con fecha futura marcada como recurrente es la primera ocurrencia de su
    propio plan: sin esta supresión aparecería dos veces el mismo día, real y fantasma."""
    account = factories.make_account(db)
    recurrence = factories.make_recurrence(db, account_id=account.id, starts_on=date(2026, 1, 10))
    factories.make_transaction(
        db, account_id=account.id, date=date(2026, 1, 10), recurrence_id=recurrence.id
    )

    result = project(db, date(2026, 1, 1), date(2026, 3, 31))

    assert [p.date for p in result] == [date(2026, 2, 10), date(2026, 3, 10)]


def test_projected_transaction_carries_the_plan_fields(db):
    entity = factories.make_entity(db)
    account = factories.make_account(db, name="Banco Nación")
    factories.make_recurrence(
        db,
        account_id=account.id,
        entity_id=entity.id,
        description="Alquiler oficina",
        amount=Decimal("450000"),
        type=TransactionType.expense,
        starts_on=date(2026, 1, 5),
    )

    ghost = project(db, date(2026, 1, 1), date(2026, 1, 31))[0]

    assert ghost.is_projected is True
    assert ghost.description == "Alquiler oficina"
    assert ghost.amount == Decimal("450000")
    assert ghost.type == TransactionType.expense
    assert ghost.account.name == "Banco Nación"
    assert ghost.entity.id == entity.id
    assert ghost.rhythm_label == "Mensual"


# --------------------------------------------------------------------------
# La grilla mezclada
# --------------------------------------------------------------------------


def test_past_period_leaves_the_grid_untouched(db):
    """La propiedad que hace segura la feature: mirando el pasado no cambia nada.

    Sin una sola ocurrencia futura que generar, la grilla vuelve al camino de siempre —el que
    pagina con LIMIT/OFFSET— y ni siquiera consulta las recurrencias.
    """
    account = factories.make_account(db)
    factories.make_recurrence(db, account_id=account.id, starts_on=date(2020, 1, 1))
    factories.make_transaction(db, account_id=account.id, date=date(2020, 6, 15))

    context = rows_context(
        db, _period(date(2020, 1, 1), date(2020, 12, 31)), TransactionFilters(), page=1
    )

    assert context["filtered_count"] == 1
    assert all(not row.is_projected for row in context["transactions"])


def test_future_period_merges_ghosts_in_date_order(db):
    account = factories.make_account(db)
    today = date.today()
    factories.make_recurrence(
        db,
        account_id=account.id,
        description="Alquiler",
        starts_on=today + timedelta(days=3),
        interval_unit=IntervalUnit.day,
        interval_count=10,
    )
    factories.make_transaction(
        db, account_id=account.id, date=today + timedelta(days=5), description="Real"
    )

    context = rows_context(
        db, _period(today, today + timedelta(days=20)), TransactionFilters(), page=1
    )

    rows = context["transactions"]
    assert [r.date for r in rows] == sorted(r.date for r in rows)
    assert [r.is_projected for r in rows] == [True, False, True]
    assert context["filtered_count"] == 3


def test_real_row_comes_before_the_ghost_of_the_same_day(db):
    account = factories.make_account(db)
    same_day = date.today() + timedelta(days=4)
    factories.make_recurrence(db, account_id=account.id, starts_on=same_day)
    factories.make_transaction(db, account_id=account.id, date=same_day)

    context = rows_context(db, _period(date.today(), same_day), TransactionFilters(), page=1)

    assert [r.is_projected for r in context["transactions"]] == [False, True]


def test_ghosts_count_towards_pagination(db):
    """Si los fantasmas no entraran en el conteo, la última página quedaría fuera de alcance:
    el paginador se arma con `filtered_count` y la grilla se corta donde dice el número."""
    account = factories.make_account(db)
    today = date.today()
    factories.make_recurrence(
        db,
        account_id=account.id,
        starts_on=today + timedelta(days=1),
        interval_unit=IntervalUnit.day,
    )

    context = rows_context(
        db, _period(today, today + timedelta(days=59)), TransactionFilters(), page=2
    )

    assert context["filtered_count"] == 59
    assert context["total_pages"] == 2
    assert len(context["transactions"]) == 9
    assert all(row.is_projected for row in context["transactions"])


# --------------------------------------------------------------------------
# Las pantallas
#
# Jinja se traga los undefined: una clave mal escrita en el contexto no explota, renderiza
# vacío. Estos tests existen para que el cableado —rutas, contextos, includes— se rompa acá y
# no en la pantalla.
# --------------------------------------------------------------------------


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


def test_recurrences_page_lists_the_plans(client, db):
    account = factories.make_account(db)
    factories.make_recurrence(db, account_id=account.id, description="Alquiler oficina")

    response = client.get("/recurrences/")

    assert response.status_code == 200
    assert "Alquiler oficina" in response.text
    assert "Mensual" in response.text


def test_recurrence_form_renders_for_new_and_for_edit(client, db):
    account = factories.make_account(db)
    recurrence = factories.make_recurrence(db, account_id=account.id, interval_count=2)

    assert client.get("/recurrences/new-form").status_code == 200

    response = client.get(f"/recurrences/{recurrence.id}/edit-form")
    assert response.status_code == 200
    assert 'value="2"' in response.text


def test_toggle_pauses_and_resumes(client, db):
    account = factories.make_account(db)
    recurrence = factories.make_recurrence(db, account_id=account.id)

    assert client.post(f"/recurrences/{recurrence.id}/toggle").status_code == 200
    db.refresh(recurrence)
    assert recurrence.is_active is False

    client.post(f"/recurrences/{recurrence.id}/toggle")
    db.refresh(recurrence)
    assert recurrence.is_active is True


def test_ends_on_before_starts_on_comes_back_as_a_toast(client, db):
    """El mensaje tiene que volver sobre el modal abierto, no como el `<h1>` del handler
    global: en un formulario, esa pared no deja dónde volver a intentar."""
    account = factories.make_account(db)

    response = client.post(
        "/recurrences/create",
        data={
            "description": "Imposible",
            "amount": "1000",
            "transaction_type": "expense",
            "account_id": str(account.id),
            "interval_unit": "month",
            "interval_count": "1",
            "starts_on": "2026-06-01",
            "ends_on": "2026-01-01",
        },
    )

    assert response.status_code == 200
    assert "showToast" in response.headers["HX-Trigger"]
    assert recurrence_crud.get_all(db) == []


def test_grid_renders_the_ghost_row(client, db):
    account = factories.make_account(db)
    today = date.today()
    factories.make_recurrence(
        db, account_id=account.id, description="Alquiler oficina", starts_on=today
    )

    response = client.get(
        "/transactions/rows",
        params={
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=40)).isoformat(),
        },
    )

    assert response.status_code == 200
    assert "Alquiler oficina" in response.text
    assert "Previsto" in response.text


def test_creating_a_transaction_with_a_rhythm_creates_and_links_the_plan(client, db):
    account = factories.make_account(db)

    response = client.post(
        "/transactions/create",
        data={
            "transaction_date": "2026-09-05",
            "description": "Alquiler",
            "amount": "450000",
            "transaction_type": "expense",
            "account_id": str(account.id),
            "repeat_unit": "month",
            "repeat_count": "1",
        },
    )

    assert response.status_code == 200
    recurrence = recurrence_crud.get_all(db)[0]
    assert recurrence.description == "Alquiler"
    assert recurrence.amount == Decimal("450000")
    assert recurrence.starts_on == date(2026, 9, 5)
    transaction = transaction_crud.get_all(db)[0]
    assert transaction.recurrence_id == recurrence.id


def test_choosing_no_repeat_pauses_the_plan_instead_of_deleting_it(client, db):
    """Borrarlo dispararía el `SET NULL` y se perdería qué transacciones eran de la serie."""
    account = factories.make_account(db)
    recurrence = factories.make_recurrence(db, account_id=account.id)
    transaction = factories.make_transaction(db, account_id=account.id, recurrence_id=recurrence.id)

    response = client.patch(
        f"/transactions/{transaction.id}/update",
        data={
            "transaction_date": str(transaction.date),
            "description": transaction.description,
            "amount": str(transaction.amount),
            "transaction_type": transaction.type.value,
            "account_id": str(account.id),
            "repeat_unit": "",
        },
    )

    assert response.status_code == 200
    db.refresh(recurrence)
    assert recurrence.is_active is False
    db.refresh(transaction)
    assert transaction.recurrence_id == recurrence.id
