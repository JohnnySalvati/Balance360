from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.models.import_batch import ImportBatch
from balance360.schemas.import_batch import ImportBatchCreate, ImportBatchUpdate


def create(db: Session, data: ImportBatchCreate) -> ImportBatch:
    db_import_batch = ImportBatch(**data.model_dump())
    db.add(db_import_batch)
    db.flush()
    db.refresh(db_import_batch)
    return db_import_batch


def delete(db: Session, import_batch: ImportBatch):
    db.delete(import_batch)
    db.flush()


def update(db: Session, data: ImportBatchUpdate, import_batch: ImportBatch) -> ImportBatch:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(import_batch, field, value)
    db.flush()
    db.refresh(import_batch)
    return import_batch


def get_all(db: Session) -> list[ImportBatch]:
    import_baches = db.execute(select(ImportBatch)).scalars().all()
    return list(import_baches)


def get_by_id(db: Session, import_batch_id: UUID) -> ImportBatch | None:
    return (
        db.execute(select(ImportBatch).where(ImportBatch.id == import_batch_id)).scalars().first()
    )
