from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    database_url: str
    database_test_url: str | None = None
    homo_private_key_path: Path | None = None
    prod_private_key_path: Path | None = None
    homo_cert_path: Path | None = None
    prod_cert_path: Path | None = None
    SECRET_KEY: str
    afip_env: Literal["homo", "prod"]

    # SMTP. Opcionales a proposito: sin esto la app tiene que arrancar igual en
    # desarrollo y en los tests. La ausencia se valida al momento de enviar, en
    # services/email.py, que devuelve un EmailError legible en vez de un
    # AttributeError sobre None a mitad del handshake.
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    @property
    def smtp_configured(self) -> bool:
        return all([self.smtp_host, self.smtp_user, self.smtp_password, self.smtp_from])

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+psycopg://", 1)
        elif value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+psycopg://", 1)
        return value

    @property
    def private_key_path(self):
        if self.afip_env == "homo":
            return self.homo_private_key_path
        else:
            return self.prod_private_key_path

    @property
    def cert_path(self):
        if self.afip_env == "homo":
            return self.homo_cert_path
        else:
            return self.prod_cert_path


settings = Settings()  # type: ignore
engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
