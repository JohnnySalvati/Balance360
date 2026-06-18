from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    database_url: str
    database_test_url: str|None = None
    private_key_path: Path
    cert_path: Path


settings = Settings() # type: ignore
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False, 
    autoflush=False
    )