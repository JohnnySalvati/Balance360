import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.contact import Contact
from balance360.schemas.contact import ContactCreate, ContactUpdate

def get_all(db: Session) -> list[Contact]:
    contacts = db.execute(select(Contact)).scalars().all()
    return list(contacts)

def get_by_id(db: Session, contact_id: uuid.UUID) -> Contact | None:
    contact = db.execute(select(Contact).where(Contact.id == contact_id)).scalars().first()
    return contact

def get_by_tax_id(db: Session, tax_id: str) -> Contact | None:
    return db.execute(select(Contact).where(Contact.tax_id == tax_id)).scalars().first()

def create(db: Session, data: ContactCreate) -> Contact:
    db_contact = Contact(**data.model_dump())
    db.add(db_contact)
    db.flush()
    db.refresh(db_contact)
    return db_contact

def delete(db: Session, contact: Contact):
    db.delete(contact)
    db.flush()

def update(db: Session, contact: Contact, data: ContactUpdate) -> Contact:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.flush()
    db.refresh(contact)
    return contact


