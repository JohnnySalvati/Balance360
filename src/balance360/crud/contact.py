import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from balance360.models.contact import Contact
from balance360.schemas.contact import ContactCreate, ContactUpdate
from balance360.services.text import digits_only


def get_all(db: Session, search: str | None = None) -> list[Contact]:
    stmt = select(Contact)
    if search:
        stmt = stmt.where(
            or_(
                Contact.name.ilike(f"%{search}%"),
                Contact.trade_name.ilike(f"%{search}%"),
            )
        )

    contacts = db.execute(stmt.order_by(Contact.name)).scalars().all()
    return list(contacts)


def get_by_id(db: Session, contact_id: uuid.UUID) -> Contact | None:
    contact = db.execute(select(Contact).where(Contact.id == contact_id)).scalars().first()
    return contact


def get_by_tax_id(db: Session, tax_id: str, exclude_id: uuid.UUID | None = None) -> Contact | None:
    """El contacto que tiene ese CUIT, o None.

    `exclude_id` es para la edición: al validar un contacto contra sí mismo, "ya existe uno
    con este CUIT" siempre sería verdad —es él— y no se podría guardar ningún otro cambio.
    """
    stmt = select(Contact).where(Contact.tax_id == digits_only(tax_id))
    if exclude_id is not None:
        stmt = stmt.where(Contact.id != exclude_id)
    return db.execute(stmt).scalars().first()


def create(db: Session, data: ContactCreate) -> Contact:
    db_contact = Contact(**data.model_dump())
    db.add(db_contact)
    db.flush()
    db.refresh(db_contact)
    return db_contact


def delete(db: Session, contact: Contact) -> None:
    db.delete(contact)
    db.flush()


def update(db: Session, contact: Contact, data: ContactUpdate) -> Contact:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.flush()
    db.refresh(contact)
    return contact
