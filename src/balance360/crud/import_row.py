from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.enums import ImportRowStatus
from balance360.models.import_row import ImportRow
from balance360.schemas.import_row import ImportRowCreate, ImportRowUpdate


def create(db: Session, data: ImportRowCreate) -> ImportRow:
    import_row = ImportRow(**data.model_dump())
    db.add(import_row)
    db.flush()
    db.refresh(import_row)
    return import_row


def delete(db: Session, import_row: ImportRow):
    db.delete(import_row)
    db.flush()


def get_by_id(db: Session, import_row_id: UUID) -> ImportRow | None:
    return db.execute(select(ImportRow).where(ImportRow.id == import_row_id)).scalars().first()


def get_by_batch(
    db: Session, import_batch_id: UUID, status: ImportRowStatus | None = None
) -> list[ImportRow]:
    stmt = select(ImportRow).where(ImportRow.batch_id == import_batch_id)

    if status:
        stmt = stmt.filter(ImportRow.status == status)

    import_rows = db.execute(stmt).scalars().all()
    return list(import_rows)


def update(db: Session, data: ImportRowUpdate, import_row: ImportRow) -> ImportRow:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(import_row, field, value)
    db.flush()
    db.refresh(import_row)
    return import_row
