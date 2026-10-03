"""Importar filas en revisión: lo que vale es la grilla, y es todo o nada.

El caso que lo motivó: filas de AOMA Bs. As. parseadas con el importe en `debit` e
importadas en masa como Ingreso. La ruta vieja buscaba el monto en `credit`, no lo
encontraba, salteaba la fila en silencio y contestaba 200 igual: las filas quedaban
pendientes y nadie se enteraba de por qué.
"""

import datetime
import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from balance360.crud import import_row as import_row_crud
from balance360.enums import ImportRowStatus, TransactionType
from balance360.exceptions import ImportRowValidationError
from balance360.models.import_batch import ImportBatch
from balance360.models.import_row import ImportRow
from balance360.models.transaction import Transaction
from balance360.services.import_row import ImportRowInput, import_rows
from tests import factories


def _make_batch(db):
    batch = ImportBatch(id=uuid.uuid4(), filename="movimientos.xlsx")
    db.add(batch)
    db.flush()
    return batch


def _make_row(db, batch, account, source_row=1, description="AOMA Bsas", **kwargs):
    row = ImportRow(
        id=uuid.uuid4(),
        batch_id=batch.id,
        account_id=account.id,
        source_row=source_row,
        date=kwargs.pop("date", datetime.date(2026, 9, 1)),
        description=description,
        debit=kwargs.pop("debit", Decimal("1500")),
        credit=kwargs.pop("credit", None),
        status=kwargs.pop("status", ImportRowStatus.needs_review),
        reason="Importes invalidos",
    )
    db.add(row)
    db.flush()
    return row


def _input(row, account, **overrides):
    values = {
        "row_id": row.id,
        "date": "2026-09-01",
        "description": row.description,
        "amount": "1500",
        "type": "income",
        "account_id": str(account.id),
    }
    values.update(overrides)
    return ImportRowInput(**values)


def _transactions(db):
    return list(db.execute(select(Transaction)).scalars().all())


# ── Servicio ──────────────────────────────────────────────────────────────────


def test_importa_como_ingreso_una_fila_parseada_con_el_monto_en_debit(db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    row = _make_row(db, batch, account, debit=Decimal("1500"), credit=None)

    [transaction] = import_rows(db, [_input(row, account, type="income")])

    assert transaction.type == TransactionType.income
    assert transaction.amount == Decimal("1500.00")
    assert transaction.import_row_id == row.id
    assert row.status == ImportRowStatus.imported


def test_lo_editado_en_la_grilla_gana_sobre_lo_parseado(db):
    account = factories.make_account(db)
    other = factories.make_account(db, name="Otra", currency_id=account.currency_id)
    batch = _make_batch(db)
    row = _make_row(db, batch, account)

    [transaction] = import_rows(
        db,
        [
            _input(
                row,
                other,
                date="2026-09-15",
                description="  AOMA cuota septiembre  ",
                amount="2000.555",
                type="expense",
            )
        ],
    )

    assert transaction.account_id == other.id
    assert transaction.date == datetime.date(2026, 9, 15)
    assert transaction.description == "AOMA cuota septiembre"
    assert transaction.amount == Decimal("2000.56")  # money(): ROUND_HALF_UP
    assert transaction.type == TransactionType.expense
    # La traza apunta al Excel original, no a la cuenta elegida.
    assert transaction.source_sheet == account.name
    assert transaction.source_file == "movimientos.xlsx"


def test_una_fila_invalida_frena_todo_el_lote(db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    good = _make_row(db, batch, account, source_row=1, description="Buena")
    bad = _make_row(db, batch, account, source_row=2, description="Mala")

    with pytest.raises(ImportRowValidationError) as exc:
        import_rows(db, [_input(good, account), _input(bad, account, amount="")])

    assert _transactions(db) == []
    assert good.status == ImportRowStatus.needs_review
    assert bad.status == ImportRowStatus.needs_review
    message = str(exc.value)
    assert message.startswith("No se importó nada.")
    assert '"Mala": falta el monto' in message
    assert "Buena" not in message


def test_el_mensaje_junta_todos_los_errores_de_todas_las_filas(db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    row = _make_row(db, batch, account)

    with pytest.raises(ImportRowValidationError) as exc:
        import_rows(
            db,
            [_input(row, account, date="", amount="-5", type="otro", account_id="")],
        )

    message = str(exc.value)
    for fragment in (
        "falta la fecha",
        "el monto tiene que ser mayor a cero",
        "el tipo no es válido",
        "falta la cuenta",
    ):
        assert fragment in message


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"date": "31/12/2026"}, "la fecha no es válida"),
        ({"amount": "abc"}, "el monto no es válido"),
        ({"amount": "NaN"}, "el monto no es válido"),
        ({"amount": "0"}, "el monto tiene que ser mayor a cero"),
        ({"description": "   "}, "falta la descripción"),
        ({"description": "x" * 201}, "la descripción supera los 200 caracteres"),
        ({"account_id": str(uuid.uuid4())}, "la cuenta no existe"),
    ],
)
def test_validaciones_por_campo(db, overrides, expected):
    account = factories.make_account(db)
    batch = _make_batch(db)
    row = _make_row(db, batch, account)

    with pytest.raises(ImportRowValidationError, match=expected):
        import_rows(db, [_input(row, account, **overrides)])


def test_una_fila_ya_importada_no_se_importa_dos_veces(db):
    """Pestaña vieja o doble click: la fila ya no está pendiente."""
    account = factories.make_account(db)
    batch = _make_batch(db)
    row = _make_row(db, batch, account)
    import_rows(db, [_input(row, account)])

    with pytest.raises(ImportRowValidationError, match="ya no está pendiente"):
        import_rows(db, [_input(row, account)])

    assert len(_transactions(db)) == 1


def test_el_mismo_id_repetido_crea_una_sola_transaccion(db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    row = _make_row(db, batch, account)

    import_rows(db, [_input(row, account), _input(row, account)])

    assert len(_transactions(db)) == 1


def test_el_mensaje_se_corta_a_cinco_filas(db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    rows = [_make_row(db, batch, account, source_row=i, description=f"F{i}") for i in range(7)]

    with pytest.raises(ImportRowValidationError) as exc:
        import_rows(db, [_input(r, account, amount="") for r in rows])

    assert "y 2 más" in str(exc.value)
    assert '"F5"' not in str(exc.value)


def test_get_by_batch_respeta_el_orden_de_la_planilla(db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    for source_row in (5, 1, 3):
        _make_row(db, batch, account, source_row=source_row)

    rows = import_row_crud.get_by_batch(db, batch.id, ImportRowStatus.needs_review)

    assert [r.source_row for r in rows] == [1, 3, 5]


# ── Rutas ─────────────────────────────────────────────────────────────────────


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


def _bulk_form(rows, account, **overrides):
    """Lo que manda htmx: listas paralelas, una entrada por fila tildada."""
    form = {
        "row_ids": [str(r.id) for r in rows],
        "transaction_date": ["2026-09-01"] * len(rows),
        "description": [r.description for r in rows],
        "amount": ["1500"] * len(rows),
        "type": ["income"] * len(rows),
        "account_id": [str(account.id)] * len(rows),
    }
    form.update(overrides)
    return form


def test_bulk_importa_con_los_valores_de_cada_fila(client, db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    first = _make_row(db, batch, account, source_row=1, description="Uno")
    second = _make_row(db, batch, account, source_row=2, description="Dos")
    pending = _make_row(db, batch, account, source_row=3, description="Queda")

    form = _bulk_form([first, second], account, type=["income", "expense"], amount=["10", "20"])
    response = client.post("/imports/rows/bulk-import", data=form, headers={"HX-Request": "true"})

    assert response.status_code == 200
    toast = json.loads(response.headers["HX-Trigger"])["showToast"]
    assert toast == {"message": "Se importaron 2 transacción(es).", "type": "success"}
    by_description = {t.description: t for t in _transactions(db)}
    assert by_description["Uno"].type == TransactionType.income
    assert by_description["Uno"].amount == Decimal("10.00")
    assert by_description["Dos"].type == TransactionType.expense
    # La grilla que vuelve tiene solo lo que sigue pendiente.
    assert str(pending.id) in response.text
    assert str(first.id) not in response.text


def test_bulk_con_un_error_no_toca_la_grilla_ni_crea_nada(client, db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    rows = [_make_row(db, batch, account, source_row=i, description=f"F{i}") for i in (1, 2)]

    form = _bulk_form(rows, account, transaction_date=["2026-09-01", ""])
    response = client.post("/imports/rows/bulk-import", data=form, headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert response.headers["HX-Reswap"] == "none"
    toast = json.loads(response.headers["HX-Trigger"])["showToast"]
    assert toast["type"] == "error"
    assert '"F2": falta la fecha' in toast["message"]
    assert _transactions(db) == []


def test_bulk_con_listas_desparejas_no_importa_nada(client, db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    rows = [_make_row(db, batch, account, source_row=i) for i in (1, 2)]

    form = _bulk_form(rows, account, amount=["10"])
    response = client.post("/imports/rows/bulk-import", data=form, headers={"HX-Request": "true"})

    assert response.headers["HX-Reswap"] == "none"
    assert "incompleto" in json.loads(response.headers["HX-Trigger"])["showToast"]["message"]
    assert _transactions(db) == []


def test_importar_una_fila_con_el_monto_vacio_avisa_en_vez_de_dar_500(client, db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    row = _make_row(db, batch, account)

    response = client.post(
        f"/imports/rows/{row.id}/import",
        data={
            "transaction_date": "2026-09-01",
            "description": "AOMA Bsas",
            "amount": "",
            "type": "income",
            "account_id": str(account.id),
        },
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert response.headers["HX-Reswap"] == "none"
    assert "falta el monto" in response.headers["HX-Trigger"]
    assert row.status == ImportRowStatus.needs_review


def test_importar_una_fila(client, db):
    account = factories.make_account(db)
    batch = _make_batch(db)
    row = _make_row(db, batch, account)

    response = client.post(
        f"/imports/rows/{row.id}/import",
        data={
            "transaction_date": "2026-09-01",
            "description": "AOMA Bsas",
            "amount": "1500",
            "type": "income",
            "account_id": str(account.id),
        },
    )

    assert response.status_code == 200
    assert row.status == ImportRowStatus.imported
    assert len(_transactions(db)) == 1
