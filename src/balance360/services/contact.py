"""Reglas del alta y la edición de un contacto.

Hoy la única es que el CUIT no se repita, y existe porque ya pasó: se cargaron dos fichas del
mismo sujeto —"AOMA Bs. As." y "Asociacion Obrera Minera Argentina", los dos con el CUIT
30503218107— y los comprobantes se repartieron entre las dos sin que nadie lo notara hasta que
un reporte por contacto mostró la mitad de la facturación de un cliente.

El índice único de `contacts.tax_id` es la garantía de verdad; esto es lo que la convierte en
un mensaje que se puede leer. Las dos capas son necesarias y no se reemplazan: sin el índice,
dos requests concurrentes pasan los dos por acá y los dos insertan; sin esto, el índice tira un
`IntegrityError` que sale como "No se pudo completar la operación" y no dice cuál era el
contacto que ya estaba.
"""

import uuid

from sqlalchemy.orm import Session

from balance360.crud import contact as contact_crud
from balance360.exceptions import ContactDuplicateTaxIdError
from balance360.models.contact import Contact
from balance360.schemas.contact import ContactCreate, ContactUpdate
from balance360.services.text import format_cuit


def validate_unique_tax_id(
    db: Session, tax_id: str | None, exclude_id: uuid.UUID | None = None
) -> None:
    """Lanza si otro contacto ya tiene ese CUIT. Sin CUIT no valida nada.

    El contacto sin CUIT es legítimo y frecuente —el consumidor final, la persona a la que no
    se le factura— así que ahí no hay nada que sea único.
    """
    if not tax_id:
        return

    existing = contact_crud.get_by_tax_id(db, tax_id, exclude_id=exclude_id)
    if existing is not None:
        raise ContactDuplicateTaxIdError(
            f'El CUIT {format_cuit(existing.tax_id)} ya está cargado en "{existing.name}". '
            "Usá ese contacto o corregí el número."
        )


def create(db: Session, data: ContactCreate) -> Contact:
    validate_unique_tax_id(db, data.tax_id)
    return contact_crud.create(db, data)


def update(db: Session, contact: Contact, data: ContactUpdate) -> Contact:
    # `exclude_unset` y no el `tax_id` pelado: un PATCH que no manda el campo no lo está
    # cambiando, y validar el que ya tiene contra sí mismo no aporta nada.
    if "tax_id" in data.model_dump(exclude_unset=True):
        validate_unique_tax_id(db, data.tax_id, exclude_id=contact.id)
    return contact_crud.update(db, contact, data)
