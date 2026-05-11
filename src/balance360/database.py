from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    database_url: str

settings = Settings() # type: ignore
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False, 
    autoflush=False
    )