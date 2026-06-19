from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.import_row import ImportRow
from balance360.schemas.import_row import ImportRowCreate

def create(db: Session, data: ImportRowCreate) -> ImportRow:
    import_row = ImportRow(**data.model_dump())
    db.add(import_row)
    db.flush()
    db.refresh(import_row)
    return import_row

def delete(db: Session, import_row: ImportRow):
    db.delete(import_row)
    db.flush()