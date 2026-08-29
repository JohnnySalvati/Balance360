import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from balance360.models.base import Base
from balance360.services.rate_limit import reset_all


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_test_url: str


@pytest.fixture(scope="session")
def engine():
    settings = Settings()  # type: ignore
    engine = create_engine(settings.database_test_url)
    return engine


@pytest.fixture(scope="session")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


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
