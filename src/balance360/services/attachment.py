"""Guardar y borrar el archivo físico detrás de un `Attachment`.

El modelo `Attachment` guarda metadatos (nombre original, `stored_filename`, tamaño,
mime); los bytes viven en `settings.attachments_dir`. Se separan la fila y el archivo a
propósito: la fila es transaccional (rollback si falla la creación del invoice), el
archivo no. La regla que evita que se acumule basura es escribir el archivo PRIMERO y la
fila DESPUÉS, así el rollback del invoice nunca deja fila colgada y, si algo falla entre
medio, lo peor que queda es un archivo huérfano —trivial de detectar y limpiar—.
"""

from __future__ import annotations

import mimetypes
import os
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from balance360.database import settings
from balance360.models.attachment import Attachment
from balance360.models.invoice import Invoice


def _guess_mime(filename: str) -> str:
    """`.pdf` → `application/pdf`, y así para lo que Python conoce; sin match, octet-stream
    (el rechazo elegante en tiempo de servir, no acá)."""
    guess, _ = mimetypes.guess_type(filename)
    return guess or "application/octet-stream"


def save(
    db: Session,
    invoice: Invoice,
    original_filename: str,
    content: bytes,
    mime_type: str | None = None,
) -> Attachment:
    """Adjuntar `content` a `invoice`. Devuelve el `Attachment` ya en la sesión.

    El nombre en disco es un UUID con la extensión del original, para no depender de que
    dos archivos con el mismo nombre no se pisen y para no escribir en disco algo que la
    persona tipeó. `settings.attachments_dir` se crea si no existe.
    """
    settings.attachments_dir.mkdir(parents=True, exist_ok=True)
    extension = os.path.splitext(original_filename)[1].lower()
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    (settings.attachments_dir / stored_filename).write_bytes(content)

    attachment = Attachment(
        invoice_id=invoice.id,
        filename=original_filename[:255],
        stored_filename=stored_filename,
        mime_type=(mime_type or _guess_mime(original_filename))[:100],
        file_size=len(content),
    )
    db.add(attachment)
    db.flush()
    return attachment


def path_of(attachment: Attachment) -> Path:
    """Ruta absoluta del archivo detrás del `Attachment`."""
    return settings.attachments_dir / attachment.stored_filename
