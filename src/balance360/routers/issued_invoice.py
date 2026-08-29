"""La puerta por la que FactuMov registra acá lo que emitió.

Es el único router de `/api` que no es un CRUD: no expone una tabla, recibe un hecho. Por eso
tiene un solo endpoint y un schema propio en vez de reusar `InvoiceCreate` — lo que llega no
son los campos de esta base, es un comprobante descripto en los términos de la otra app.
"""

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from balance360.dependencies import get_api_user, get_db
from balance360.models.user import User
from balance360.schemas.issued_invoice import IssuedInvoiceCreate, IssuedInvoiceRead
from balance360.services import issued_invoice as issued_invoice_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["issued-invoices"])


@router.post("/issued", response_model=IssuedInvoiceRead, status_code=201)
def register_issued_invoice(
    data: IssuedInvoiceCreate,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_api_user),
) -> IssuedInvoiceRead:
    """Registra un comprobante que ya fue autorizado por ARCA en otra app.

    **201 la primera vez, 200 el reintento.** Los dos son éxito y el que llama los trata
    igual; la diferencia existe para que el reintento se pueda leer en un log de acceso sin
    confundirlo con un alta duplicada.

    Los errores suben como `IssuedInvoiceError` y los convierte el handler global de
    `main.py`, que para `/api` responde JSON. Atraparlos acá para reescribir el mensaje sería
    perder lo único que le sirve al usuario del otro lado: qué falta cargar en Balance360.

    `get_api_user` ya corre en el `include_router`; se vuelve a pedir acá porque hace falta el
    usuario y no solo su validación. FastAPI cachea la dependencia, así que se resuelve una
    sola vez por request.
    """
    invoice, already_registered = issued_invoice_service.register(db, user, data)

    if already_registered:
        response.status_code = 200
    else:
        logger.info(
            "Registrado el comprobante %s %s-%s como %s, entidad %s.",
            invoice.voucher_type.value if invoice.voucher_type else "?",
            invoice.pos,
            invoice.number,
            invoice.id,
            invoice.entity.name,
        )

    return IssuedInvoiceRead(
        id=invoice.id,
        entity_id=invoice.entity_id,
        entity_name=invoice.entity.name,
        contact_id=invoice.contact_id,
        already_registered=already_registered,
    )
