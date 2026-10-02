import unicodedata
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from balance360.models.contact import Contact
from balance360.schemas.contact import ContactCreate, ContactUpdate
from balance360.services.text import digits_only

# Las tildes quedan fuera de la comparación: "asociacion" tiene que encontrar
# "Asociación", que es como está escrito el nombre real. Se hace con el translate() de
# Postgres y no con la extensión `unaccent` para no depender de un CREATE EXTENSION —lo
# corre el superusuario, y el de producción no es el de la aplicación— y que dev y
# producción busquen igual sin un paso de instalación que recordar.
_ACCENTED = "áàäâãéèëêíìïîóòöôõúùüûñçÁÀÄÂÃÉÈËÊÍÌÏÎÓÒÖÔÕÚÙÜÛÑÇ"
_PLAIN = "".join(unicodedata.normalize("NFD", letter)[0] for letter in _ACCENTED)


def _without_accents(text: str) -> str:
    """La misma transformación que `_PLAIN`, del lado de Python.

    Las dos puntas tienen que normalizarse igual: si solo se normalizara la columna,
    buscar "Asociación" tal cual está escrito dejaría de encontrarla.
    """
    return "".join(unicodedata.normalize("NFD", letter)[0] for letter in text)


def get_all(db: Session, search: str | None = None) -> list[Contact]:
    stmt = select(Contact)
    if search:
        pattern = f"%{_without_accents(search)}%"
        stmt = stmt.where(
            or_(
                func.translate(Contact.name, _ACCENTED, _PLAIN).ilike(pattern),
                func.translate(Contact.trade_name, _ACCENTED, _PLAIN).ilike(pattern),
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
