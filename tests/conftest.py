import os

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from balance360.models.base import Base
from balance360.services.rate_limit import reset_all

# Un esquema por proceso, para que dos corridas simultáneas no se pisen.
#
# Antes las tablas vivían en `public` de `balance360_test`, que es una sola para todos:
# el fixture de sesión las crea al arrancar y las dropea al terminar, sin nada atado al
# proceso. Dos corridas a la vez —dos terminales, dos ventanas de Claude sobre el mismo
# repo— compartían esas tablas, y la que terminaba primero se las dropeaba a la otra por
# abajo. La víctima moría con `UndefinedTable: relation "users" does not exist` en el
# medio de una corrida sana, nombrando cualquier tabla, y eso no se lee como un problema
# de infraestructura: se lee como una regresión del diff que uno tiene abierto.
#
# El esquema lleva el PID, así que cada proceso crea el suyo y solo dropea el suyo. El
# `DROP ... IF EXISTS` de la creación es para el PID reciclado: si una corrida murió a lo
# bruto y dejó el esquema colgado, la que hereda ese número lo limpia en vez de encontrarse
# con las tablas de un muerto.
SCHEMA = f"test_{os.getpid()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_test_url: str


@pytest.fixture(scope="session")
def engine():
    """El engine de la corrida, clavado a su esquema.

    `search_path` lleva **solo** el esquema propio, sin `public` de fallback a propósito:
    `create_all` pregunta primero si la tabla existe y lo hace con visibilidad de
    `search_path`, así que con `public` adentro vería las tablas viejas que quedaron ahí,
    las daría por creadas y los tests terminarian escribiendo en la base compartida — que
    es exactamente lo que esto viene a evitar.
    """
    settings = Settings()  # type: ignore
    return create_engine(
        settings.database_test_url,
        connect_args={"options": f"-csearch_path={SCHEMA}"},
    )


@pytest.fixture(scope="session")
def tables(engine):
    with engine.connect() as connection:
        connection.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
        connection.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))
        connection.commit()

    Base.metadata.create_all(engine)
    yield

    # `DROP SCHEMA ... CASCADE` en vez de `Base.metadata.drop_all`: se lleva todo lo que
    # haya adentro —tablas, enums, lo que un modelo que nadie importó haya dejado— sin
    # depender de que `Base.metadata` esté completa ni de resolver el orden de las FK.
    with engine.connect() as connection:
        connection.execute(text(f'DROP SCHEMA "{SCHEMA}" CASCADE'))
        connection.commit()


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Los limitadores son globales de módulo: sin esto, el que gasta la ventana se la deja
    gastada al test siguiente, y el que falla no es el que lo rompió."""
    reset_all()
    yield
    reset_all()


@pytest.fixture(scope="function")
def db(engine, tables):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def _fake_ticket(monkeypatch):
    # _build_invoice_request calls get_access_ticket("wsfe"); keep it off the network.
    monkeypatch.setattr(
        "balance360.services.invoice.get_access_ticket",
        lambda service: {"token": "tok", "sign": "sig"},
    )
