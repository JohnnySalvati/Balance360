"""Registrar acá un comprobante que ya emitió FactuMov.

El comprobante **ya existe**: tiene CAE, tiene número y no se puede modificar ni anular desde
esta app. Entonces esto no es "crear una factura", es copiar un hecho consumado a la
contabilidad, y de ahí salen las cuatro decisiones que gobiernan el módulo:

1. **Entra confirmado, autorizado e impago.** Confirmado y autorizado porque las dos cosas ya
   pasaron —ARCA le puso el CAE— y dejarlo en borrador significaría que la app pide confirmar
   algo que no se puede desconfirmar. Impago porque el cobro es otro hecho, con otra fecha,
   que Balance360 registra cuando ocurre.
2. **Se verifica que los importes cierren.** Balance360 no guarda totales: los deriva de las
   líneas. Como las dos apps escriben el precio distinto (ver `_line_values`), una traducción
   mal hecha no daría error, daría un total distinto del que ARCA autorizó. Se compara y, si
   no coincide, no se guarda nada.
3. **Es idempotente por `external_id`.** El que llama reintenta cuando esto no contesta, y un
   comprobante duplicado no se puede borrar sin dejar un agujero en la numeración.
4. **Nunca pisa datos de acá.** Si el contacto ya existe, se usa como está: el CUIT alcanza
   para reconocerlo, y su ficha —categoría, mail, nombre de fantasía— la mantiene el que la
   usa todos los días, que es este lado.
"""

import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.crud import contact as contact_crud
from balance360.crud import invoice as invoice_crud
from balance360.crud import invoice_line as invoice_line_crud
from balance360.enums import ContactType, InvoiceType, IvaAliquot, VoucherType
from balance360.exceptions import (
    IssuedInvoiceConflictError,
    IssuedInvoiceError,
    IssuedInvoiceMismatchError,
)
from balance360.models.contact import Contact
from balance360.models.entity import Entity
from balance360.models.fiscal_identity import FiscalIdentity
from balance360.models.invoice import Invoice
from balance360.models.money import money
from balance360.models.user import User
from balance360.schemas.contact import ContactCreate
from balance360.schemas.invoice import InvoiceCreate
from balance360.schemas.invoice_line import InvoiceLineCreate
from balance360.schemas.issued_invoice import IssuedInvoiceCreate, IssuedInvoiceLine
from balance360.services.text import digits_only

logger = logging.getLogger(__name__)

# El nombre de la app de origen, tal como queda en `Invoice.external_source`. Constante y no
# un parámetro: hoy hay una sola integración y la columna existe para poder distinguir lo
# importado de lo que se carga a mano, no para coleccionar orígenes.
SOURCE = "factumov"

# La precisión del unitario neto que se guarda. Dos decimales no alcanzan para reexpresar en
# neto un precio que vino con el IVA adentro — el ejemplo completo está en el comentario de
# `unit_price`, en `models/invoice_line.py`.
_UNIT_PRICE_PLACES = Decimal("0.0001")

_MAX_DESCRIPTION = 200


def register(db: Session, user: User, data: IssuedInvoiceCreate) -> tuple[Invoice, bool]:
    """Registra el comprobante y devuelve `(invoice, ya_estaba)`.

    El bool distingue el alta del reintento que encontró la fila de antes. Para el que llama
    las dos son un éxito; sirve para el log y para que un reintento no se lea como duplicado.
    """
    existing = _by_external_id(db, data.external_id)
    if existing is not None:
        logger.info(
            "El comprobante %s de %s ya estaba registrado como %s.",
            data.external_id,
            SOURCE,
            existing.id,
        )
        return existing, True

    fiscal_identity = _fiscal_identity(db, data.issuer_tax_id)
    entity = _entity(user, fiscal_identity, data.entity_id)
    _check_not_taken(db, fiscal_identity, data)
    contact = _contact(db, data)

    invoice = invoice_crud.create(
        db,
        InvoiceCreate(
            invoice_type=InvoiceType.sale,
            entity_id=entity.id,
            fiscal_identity_id=fiscal_identity.id,
            contact_id=contact.id,
            category_id=data.category_id,
            date=data.date,
            # Formal y no informal: tiene CAE. `formal=False` es lo que en esta app significa
            # "sin respaldo", y al normalizar borra letra, punto de venta y número.
            formal=True,
            tax_only=False,
            voucher_type=data.voucher_type,
            pos=data.pos,
            number=data.number,
            confirmed=True,
            authorized=True,
            paid=False,
            cae=data.cae,
            cae_expiry=data.cae_expiry,
            concepto=data.concepto,
            from_date=data.from_date,
            to_date=data.to_date,
            due_date=data.due_date,
        ),
    )
    invoice.external_source = SOURCE
    invoice.external_id = data.external_id

    for line in data.lines:
        quantity, unit_price, description = _line_values(data.voucher_type, line)
        invoice_line_crud.create(
            db,
            InvoiceLineCreate(
                invoice_id=invoice.id,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                iva_aliquot=line.iva_aliquot,
            ),
        )

    db.refresh(invoice)
    _check_totals(invoice, data)
    return invoice, False


def _by_external_id(db: Session, external_id: uuid.UUID) -> Invoice | None:
    return (
        db.execute(
            select(Invoice).where(
                Invoice.external_source == SOURCE, Invoice.external_id == external_id
            )
        )
        .scalars()
        .first()
    )


def _fiscal_identity(db: Session, tax_id: str) -> FiscalIdentity:
    """La identidad fiscal de ese CUIT. **No se crea sola si no está.**

    Crearla obligaría a adivinar a qué entidad pertenece, y esa es justamente la decisión que
    define si el comprobante aparece en el balance de InSoft o en el de la Escuela. Es una
    decisión de acá, se toma una sola vez, y hasta que se tome el registro falla con un
    mensaje que dice qué cargar.
    """
    identity = (
        db.execute(select(FiscalIdentity).where(FiscalIdentity.tax_id == digits_only(tax_id)))
        .scalars()
        .first()
    )
    if identity is None:
        raise IssuedInvoiceError(
            f"El CUIT {tax_id} no está cargado como identidad fiscal en Balance360. "
            "Cargalo y asociálo a una entidad antes de registrar comprobantes suyos."
        )
    return identity


def _entity(
    user: User, fiscal_identity: FiscalIdentity, requested_id: uuid.UUID | None
) -> Entity:
    """A qué entidad va el comprobante, entre las que este usuario puede ver.

    La relación CUIT ↔ entidad es muchos-a-muchos, así que deducirla solo funciona cuando hay
    una sola candidata — el caso normal. Con dos, elegir por nuestra cuenta sería mandar plata
    al balance equivocado en silencio, así que se pide explícita.

    El filtro por membresía no es cosmético: el token actúa como un usuario, y sin esto
    cualquiera con un token registraría comprobantes contra entidades que ni siquiera puede
    abrir en la pantalla.
    """
    allowed = {membership.entity_id for membership in user.entity_memberships}
    candidates = [entity for entity in fiscal_identity.entities if entity.id in allowed]

    if requested_id is not None:
        for entity in candidates:
            if entity.id == requested_id:
                return entity
        raise IssuedInvoiceError(
            "La entidad indicada no existe, no está asociada a ese CUIT, o no tenés acceso."
        )

    if not candidates:
        raise IssuedInvoiceError(
            f"El CUIT {fiscal_identity.tax_id} no está asociado a ninguna entidad a la que "
            "tengas acceso en Balance360."
        )
    if len(candidates) > 1:
        names = ", ".join(sorted(entity.name for entity in candidates))
        raise IssuedInvoiceError(
            f"Ese CUIT factura para más de una entidad ({names}). Elegí en FactuMov cuál "
            "registra los comprobantes."
        )
    return candidates[0]


def _check_not_taken(
    db: Session, fiscal_identity: FiscalIdentity, data: IssuedInvoiceCreate
) -> None:
    """Que no haya ya un comprobante con esa letra, punto de venta y número para ese CUIT.

    Es el mismo comprobante llegando por dos caminos: alguien que lo cargó a mano acá antes de
    que existiera la integración, o una base de FactuMov restaurada que reasignó los ids.
    Guardarlo igual lo duplicaría en el libro de IVA, que es donde más caro sale.
    """
    duplicate = (
        db.execute(
            select(Invoice).where(
                Invoice.fiscal_identity_id == fiscal_identity.id,
                Invoice.voucher_type == data.voucher_type,
                Invoice.pos == data.pos,
                Invoice.number == data.number,
            )
        )
        .scalars()
        .first()
    )
    if duplicate is not None:
        raise IssuedInvoiceConflictError(
            f"El comprobante {data.voucher_type.value} {data.pos:04d}-{data.number:08d} ya "
            "está cargado en Balance360."
        )


def _contact(db: Session, data: IssuedInvoiceCreate) -> Contact:
    """El contacto del receptor: el que ya está con ese CUIT, o uno nuevo.

    Si ya está **no se toca**. Su ficha la mantiene quien la usa todos los días, y un
    comprobante viejo registrado tarde no puede revivir un domicilio viejo.
    """
    customer = data.customer
    tax_id = digits_only(customer.tax_id)
    if tax_id:
        existing = contact_crud.get_by_tax_id(db, tax_id)
        if existing is not None:
            return existing

    return contact_crud.create(
        db,
        ContactCreate(
            name=customer.name,
            tax_id=tax_id or None,
            # `customer` y no `both`: lo que llega por acá son ventas, siempre. Si además nos
            # vende, alguien lo cambia a mano una vez y esto no lo vuelve a pisar.
            contact_type=ContactType.customer,
            condicion_iva=customer.condicion_iva,
            doc_type=customer.doc_type,
            email=customer.email,
            address=customer.address,
        ),
    )


def _line_values(voucher_type: VoucherType, line: IssuedInvoiceLine) -> tuple[int, Decimal, str]:
    """Traduce una línea de FactuMov a la convención de acá: `(cantidad, unitario neto, texto)`.

    Las dos apps escriben el precio distinto, y esta función es todo el puente:

    - **FactuMov** guarda el precio *tal como se carga*: neto en la A, con el IVA adentro en
      la B y en la C. Es lo que se imprime.
    - **Balance360** guarda siempre el neto y deriva el bruto cuando la letra lo pide.

    En la A y en la C las dos convenciones coinciden, así que con cantidad entera la línea se
    copia tal cual y la pantalla de acá muestra "3 × $1.000" como corresponde.

    Los otros dos casos se **colapsan a cantidad 1**, con el importe de la línea como unitario
    y la cantidad original mudada a la descripción:

    - **La B**, porque hay que reexpresar el precio en neto y hacerlo por unidad arrastra el
      redondeo a cada unidad: con 3 × $100 el neto unitario redondeado y multiplicado por 3 se
      va del total autorizado. Con cantidad 1 el redondeo ocurre una sola vez, sobre el
      importe de la línea, que es el número que tiene que cerrar.
    - **La cantidad fraccionaria** (1,5 horas), porque acá `quantity` es entero: está atado al
      stock y a los números de serie, donde media unidad no significa nada. Truncarla —que es
      lo que hace hoy la importación de PDF— facturaría 1 hora en vez de 1,5.
    """
    amount = money(line.quantity * line.unit_price)
    is_whole = line.quantity == line.quantity.to_integral_value()
    iva_in_price = voucher_type in (VoucherType.B, VoucherType.NCB)

    if is_whole and not iva_in_price:
        return int(line.quantity), line.unit_price, _fit(line.description)

    if iva_in_price:
        rate = _rate(line.iva_aliquot)
        unit_price = (amount / (1 + rate / 100)).quantize(_UNIT_PRICE_PLACES, ROUND_HALF_UP)
    else:
        unit_price = amount

    return 1, unit_price, _fit(_with_quantity(line))


def _rate(aliquot: IvaAliquot) -> Decimal:
    # `Decimal(str(...))`: los `rate` del enum se declararon como `Decimal(10.5)` sobre un
    # float, así que arrastran la basura binaria del literal. Pasar por `str` la corta.
    return Decimal(str(aliquot.rate))


def _with_quantity(line: IssuedInvoiceLine) -> str:
    """La descripción con la cantidad y el precio originales adentro.

    Es lo único que queda del "1,5 × $8.000" cuando la línea se colapsa, así que no es
    decorativo: sin esto la línea de acá dice 1 y no hay forma de reconstruir qué se facturó
    sin abrir el PDF.
    """
    return f"{line.description} ({_number(line.quantity)} × ${_number(line.unit_price)})"


def _number(value: Decimal) -> str:
    """Formato argentino, mínimo. No reusa el filtro `amount` a propósito.

    Ese vive en `web/templating.py` —importarlo desde un servicio invertiría las capas— y
    además redondea siempre a dos decimales, que se comería el 1,5 de una cantidad.
    """
    text = f"{value.normalize():f}"
    integer, _, fraction = text.partition(".")
    grouped = f"{int(integer):,}".replace(",", ".")
    return f"{grouped},{fraction}" if fraction else grouped


def _fit(description: str) -> str:
    return description if len(description) <= _MAX_DESCRIPTION else description[:197] + "..."


def _check_totals(invoice: Invoice, data: IssuedInvoiceCreate) -> None:
    """Que lo que Balance360 deriva de las líneas sea lo que ARCA autorizó. Exacto, al centavo.

    Es la red de toda la traducción de precios. Sin esto, un error en `_line_values` no se
    manifestaría como un error sino como un total distinto, que nadie mira hasta la
    declaración del mes que viene.

    Compara los tres números y no solo el total: un neto y un IVA cruzados que sumen igual
    pasarían desapercibidos, y son justamente el error que puede cometer una conversión entre
    "el precio incluye IVA" y "no lo incluye".
    """
    net = invoice.net_total
    total = invoice.total
    iva = total - net
    expected = data.totals
    if net == expected.net and iva == expected.iva and total == expected.total:
        return
    raise IssuedInvoiceMismatchError(
        f"Los importes no coinciden con los que autorizó ARCA: acá dan neto {net}, IVA {iva}, "
        f"total {total}; el comprobante dice neto {expected.net}, IVA {expected.iva}, total "
        f"{expected.total}. No se registró nada."
    )
