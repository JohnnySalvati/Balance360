"""El comprobante que otra app ya emitió y que acá se registra. El contrato con FactuMov.

**Los enums viajan por nombre y no por valor**, y esa es la decisión con más consecuencias de
todo el archivo. `CondicionIva.FINAL` vale 6 acá y 5 en FactuMov, porque allá se corrigieron
los códigos contra la tabla de ARCA el 2026-08-27 y acá todavía no. Si el nombre viajara como
número, un consumidor final entraría a esta base como monotributista **sin error ninguno**: el
6 es un valor válido de las dos tablas, y nadie se enteraría hasta ver el libro de IVA.

Por nombre eso no puede pasar. `FINAL` es `FINAL` de los dos lados, un nombre que no existe
explota en la validación en vez de guardar otra cosa, y el día que se corrijan los códigos de
acá el contrato no se entera. Vale para `condicion_iva`, `doc_type` y `iva_aliquot`.

Las excepciones son `voucher_type` y `concepto`, que viajan por valor porque su valor **es** el
nombre legible ("A", "products") y coincide en las dos apps.
"""

import datetime
import uuid
from decimal import Decimal
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from balance360.enums import Concepto, CondicionIva, DocType, IvaAliquot, VoucherType


def _by_name(enum_cls: type[Any]) -> Callable[[Any], Any]:
    """Resuelve el miembro por nombre, dejando pasar el miembro ya resuelto.

    `Enum[nombre]` y no `Enum(valor)`: los corchetes buscan por nombre. Es el gotcha que ya
    está anotado en CLAUDE.md, y acá es justamente lo que se quiere.
    """

    def parse(value: Any) -> Any:
        if isinstance(value, enum_cls):
            return value
        try:
            return enum_cls[value]
        except (KeyError, TypeError):
            names = ", ".join(member.name for member in enum_cls)
            raise ValueError(f"{value!r} no es un valor conocido; esperaba uno de: {names}")

    return parse


CondicionIvaByName = Annotated[CondicionIva, BeforeValidator(_by_name(CondicionIva))]
DocTypeByName = Annotated[DocType, BeforeValidator(_by_name(DocType))]
IvaAliquotByName = Annotated[IvaAliquot, BeforeValidator(_by_name(IvaAliquot))]


class IssuedInvoiceCustomer(BaseModel):
    """El receptor **tal como salió impreso**, no una ficha para mantener actualizada.

    Se manda entero en vez de un id porque los dos sistemas no comparten ninguno: el cliente
    de FactuMov y el contacto de Balance360 son filas distintas de bases distintas. Lo único
    que los une es el CUIT, y con eso alcanza para no duplicar.
    """

    name: str = Field(max_length=150)
    tax_id: str | None = Field(default=None, max_length=11)
    doc_type: DocTypeByName
    condicion_iva: CondicionIvaByName
    address: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=254)


class IssuedInvoiceLine(BaseModel):
    """Una línea con la semántica de FactuMov, sin traducir.

    **`unit_price` es el precio tal como se carga allá**: neto en la A, con el IVA adentro en
    la B y en la C. Traducirlo a la convención de Balance360 —donde el unitario es siempre
    neto— es trabajo de `services/issued_invoice.py` y no del que llama, para que el día que
    cambie algo de este modelo no haya que redeployar la otra app.
    """

    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal
    iva_aliquot: IvaAliquotByName


class IssuedInvoiceTotals(BaseModel):
    """Los importes que ARCA autorizó. **Viajan para ser verificados, no para guardarse.**

    Balance360 no tiene columnas de total: los deriva de las líneas. Entonces estos tres
    números no se persisten en ningún lado — se comparan contra lo que dan las líneas que se
    acaban de crear, y si no coinciden el registro se cancela entero. Es la única forma de que
    un error de traducción de precios se note en el momento y no en la declaración mensual.
    """

    net: Decimal
    iva: Decimal
    total: Decimal


class IssuedInvoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # El id de la factura en la app de origen. Es la clave de idempotencia: el mismo
    # `external_id` dos veces devuelve el mismo comprobante en vez de duplicarlo.
    external_id: uuid.UUID
    # El CUIT del emisor. Con esto se busca acá la identidad fiscal y, por ella, la entidad:
    # FactuMov no conoce —ni tiene por qué conocer— los UUID de esta base.
    issuer_tax_id: str = Field(max_length=11)
    # Solo hace falta cuando el CUIT factura para más de una entidad y no se puede deducir.
    entity_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None

    customer: IssuedInvoiceCustomer

    voucher_type: VoucherType
    pos: int = Field(gt=0)
    number: int = Field(gt=0)
    date: datetime.date
    concepto: Concepto = Concepto.products
    from_date: datetime.date | None = None
    to_date: datetime.date | None = None
    due_date: datetime.date | None = None

    cae: str = Field(min_length=1, max_length=14)
    cae_expiry: datetime.date

    lines: list[IssuedInvoiceLine] = Field(min_length=1)
    totals: IssuedInvoiceTotals


class IssuedInvoiceRead(BaseModel):
    """Lo que se le devuelve a la app de origen: dónde quedó y qué entidad terminó siendo.

    `already_registered` es lo que distingue el registro nuevo del reintento que encontró el
    de antes. Del lado de FactuMov las dos cosas son un éxito y se marcan igual; sirve para
    el log y para que un reintento no se lea como un duplicado silencioso.
    """

    id: uuid.UUID
    entity_id: uuid.UUID
    entity_name: str
    contact_id: uuid.UUID
    already_registered: bool
