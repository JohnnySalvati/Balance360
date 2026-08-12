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
