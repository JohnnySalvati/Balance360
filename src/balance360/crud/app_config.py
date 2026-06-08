from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.app_config import AppConfig
from balance360.schemas.app_config import AppconfigUpdate

def get(db: Session) -> AppConfig:
    app_config = db.execute(select(AppConfig)).scalars().first()
    if not app_config:
        app_config = _create(db)
    return app_config

def save(db: Session, data: AppconfigUpdate) -> AppConfig:
    app_config = get(db)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(app_config, field, value)
    db.flush()
    db.refresh(app_config)
    return app_config

def _create(db: Session):
    app_config = AppConfig()
    db.add(app_config)
    db.flush()
    db.refresh(app_config)
    return app_config