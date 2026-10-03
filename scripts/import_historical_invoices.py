"""Importar comprobantes históricos (compras y ventas) desde una carpeta de PDFs.

Cada PDF se lee con `parse_invoice_file` (texto o OCR) y sólo se crea si `is_verified`
cierra al centavo contra el total impreso; lo que no verifica va al log y se salta,
sin dejar filas parciales. Es idempotente por `(external_source='historical-import',
external_id)`, donde `external_id` es un UUID v5 del path relativo — reimportar el
mismo archivo no lo duplica.

Reglas de este import (todo lo que sigue es específico para el histórico de InSoft):

- La entidad es siempre **InSoft**. El script falla si no la encuentra.
- **Ventas**: la identidad fiscal la determina el CUIT emisor del PDF, que tiene que
  ser una de las dos identidades fiscales existentes. Además se chequea que el prefijo
  del nombre del archivo (`<CUIT>_...pdf`) coincida con el CUIT que leyó el parser;
  si no, el archivo está en la carpeta equivocada y se salta.
- **Compras**: el emisor del PDF es el proveedor (se crea el `Contact` por CUIT si no
  existe). La identidad fiscal receptor se deja `NULL` — el modelo lo permite y el
  histórico no discrimina entre las dos identidades por compra.
- El `Contact` se resuelve por CUIT (índice único parcial) y se crea con los datos que
  trae el PDF cuando no existe.
- Los ítems son las `lines` del parser si con ellas cierra al centavo, si no las
  `totals_lines` (una línea por alícuota, "Según comprobante"). Al menos una de las
  dos cierra: `is_verified` garantizó eso.
- El PDF se adjunta al comprobante.
- `paid=False` por defecto: si el cobro/pago ya ocurrió, se marca desde la app.

Uso:

    uv run python scripts/import_historical_invoices.py --kind sales     ~/Ventas/2025
    uv run python scripts/import_historical_invoices.py --kind purchases ~/Compras/2025

Corre siempre en `--dry-run` salvo que se pase `--commit`; el dry-run recorre todo
igual, lo evalúa igual y lista lo que haría, pero no toca la base ni escribe archivos.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from balance360.crud import invoice as invoice_crud
from balance360.crud import invoice_line as invoice_line_crud
from balance360.database import SessionLocal
from balance360.enums import (
    CondicionIva,
    ContactType,
    DocType,
    InvoiceType,
    IvaAliquot,
    VoucherType,
)
from balance360.models.contact import Contact
from balance360.models.entity import Entity
from balance360.models.fiscal_identity import FiscalIdentity
from balance360.models.invoice import Invoice
from balance360.schemas.invoice import InvoiceCreate
from balance360.schemas.invoice_line import InvoiceLineCreate
from balance360.services import attachment as attachment_service
from balance360.services.invoice_ocr import parse_invoice_file
from balance360.services.pdf_invoice import (
    ParsedInvoice,
    ParsedInvoiceLine,
    is_verified,
    lines_gap,
)
from balance360.services.text import digits_only

ENTITY_NAME = "InSoft"
SOURCE = "historical-import"
# UUID v5 estable a partir del path relativo. Reimportar el mismo archivo no duplica;
# mover un archivo a otra carpeta lo trata como nuevo, que es lo que hace falta si
# alguna vez el original se rehizo y su copia vieja quedó en otra parte.
NAMESPACE = uuid.UUID("6f2f4d3d-a6f0-4e30-9b1d-d09b2fabc123")

_CONDICION_MAP = {
    "MONOTRIBUTO": CondicionIva.MONOTRIBUTO,
    "EXENTO": CondicionIva.EXENTO,
    "INSCRIPTO": CondicionIva.INSCRIPTO,
}

# Alícuota impresa → miembro del enum. `IvaAliquot.reduced.rate` viene de un
# `Decimal(10.5)` que arrastra ruido de float, así que la clave se normaliza a la
# forma canónica (dos decimales) para que 10.5 y 10.50 caigan en el mismo bucket.
_ALIQUOT_BY_RATE = {a.rate.quantize(Decimal("0.01")): a for a in IvaAliquot}

# Prefijo del nombre de archivo con el CUIT emisor: `<11 dígitos>_...pdf`. Sirve para el
# chequeo cruzado en ventas; en compras el prefijo también existe pero es del proveedor.
_FILENAME_TAX_ID = re.compile(r"^(\d{11})[_-]")

logger = logging.getLogger("historical_import")


@dataclass
class ImportResult:
    total: int = 0
    imported: int = 0
    skipped_existing: int = 0
    # Comprobantes que ya estaban en la base por otra fuente (carga manual, FactuMov):
    # mismos (emisor, letra, PV, número). No se crea una fila nueva; sólo se adjunta el
    # PDF si la fila existente venía sin uno.
    skipped_duplicate_formal: int = 0
    attached_to_existing: int = 0
    skipped_unverified: int = 0
    skipped_other: int = 0

    def log_summary(self) -> None:
        logger.info(
            "recorridos=%d importados=%d ya-estaban=%d ya-cargados-a-mano=%d "
            "(adjunto-agregado=%d) sin-verificar=%d otros=%d",
            self.total,
            self.imported,
            self.skipped_existing,
            self.skipped_duplicate_formal,
            self.attached_to_existing,
            self.skipped_unverified,
            self.skipped_other,
        )


def external_id_for(base_dir: Path, path: Path) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, path.relative_to(base_dir).as_posix())


def tax_id_from_filename(path: Path) -> str | None:
    match = _FILENAME_TAX_ID.match(path.name)
    return match.group(1) if match else None


def resolve_entity(db: Session, name: str = ENTITY_NAME) -> Entity:
    entity = db.execute(select(Entity).where(Entity.name == name)).scalar_one_or_none()
    if entity is None:
        raise SystemExit(f"No hay una entidad llamada {name!r}")
    return entity


def resolve_fiscal_identities(db: Session) -> dict[str, FiscalIdentity]:
    return {fi.tax_id: fi for fi in db.execute(select(FiscalIdentity)).scalars()}


def find_existing_formal_invoice(
    db: Session,
    *,
    invoice_type: InvoiceType,
    fiscal_identity_id: uuid.UUID | None,
    contact_id: uuid.UUID,
    voucher_type: VoucherType,
    pos: int,
    number: int,
) -> Invoice | None:
    """Un comprobante formal se identifica por **el CUIT que lo emite** más (letra, PV, número).

    Para ventas el emisor es la identidad fiscal (puede haber dos CUITs de InSoft que
    compartan un PV, aunque hoy no); para compras el emisor es el proveedor (dos proveedores
    pueden tener legítimamente el mismo PV + número cada uno en su propia serie, por eso
    `contact_id` discrimina).

    Devuelve la fila si ya existe —cargada a mano desde la UI, por FactuMov, o por una
    corrida previa de este script— y None si no está.
    """
    stmt = select(Invoice).where(
        Invoice.invoice_type == invoice_type,
        Invoice.voucher_type == voucher_type,
        Invoice.pos == pos,
        Invoice.number == number,
    )
    if invoice_type is InvoiceType.sale:
        stmt = stmt.where(Invoice.fiscal_identity_id == fiscal_identity_id)
    else:
        stmt = stmt.where(Invoice.contact_id == contact_id)
    return db.execute(stmt).scalar_one_or_none()


def resolve_contact(
    db: Session,
    tax_id: str,
    name: str | None,
    condicion: str | None,
    is_supplier: bool,
) -> Contact:
    """Contacto por CUIT; se crea si no existe con los datos que trae el PDF.

    Un CUIT sin nombre no bloquea la carga: se usa un placeholder ("Sin nombre (…)")
    que el operador corrige después. La condición ante IVA por defecto es INSCRIPTO
    cuando el PDF no la aclara — es lo más común para una factura A y no cambia nada
    fiscal (el `voucher_type` es lo que manda para la presentación).
    """
    contact = db.execute(select(Contact).where(Contact.tax_id == tax_id)).scalar_one_or_none()
    if contact is not None:
        return contact
    contact = Contact(
        name=(name or f"Sin nombre ({tax_id})")[:150],
        tax_id=tax_id,
        contact_type=ContactType.supplier if is_supplier else ContactType.customer,
        condicion_iva=_CONDICION_MAP.get(condicion or "", CondicionIva.INSCRIPTO),
        doc_type=DocType.CUIT,
    )
    db.add(contact)
    db.flush()
    return contact


def lines_to_use(parsed: ParsedInvoice) -> list[ParsedInvoiceLine]:
    """Los ítems que hay que persistir. Si `lines` cierra, ganan `lines` (detalle real);
    si no, `totals_lines` (que es lo que hizo verificar al comprobante)."""
    if parsed.lines:
        gap = lines_gap(parsed)
        if gap is not None and abs(gap) <= Decimal("0.01"):
            return parsed.lines
    return parsed.totals_lines


def to_int_quantity(item: ParsedInvoiceLine) -> tuple[int, Decimal, str]:
    """Adapta un `ParsedInvoiceLine` (cantidad `Decimal`) al `InvoiceLine` (cantidad `int`).

    Cantidad entera → se pasa tal cual, con el unitario tal cual. Cantidad fraccional
    (2,5 unidades) → se colapsa a **1 × importe de la línea**, y la cantidad original
    va a la descripción. Es el mismo patrón que usa el receptor de FactuMov y sale del
    hecho de que `quantity` en el modelo es entero (está atado al stock y a los seriales:
    truncar 2,5 daría de menos, redondear haría lo mismo al revés).
    """
    description = item.description or "Según comprobante"
    if item.quantity == item.quantity.to_integral_value():
        return int(item.quantity), item.unit_price, description
    amount = (item.quantity * item.unit_price).quantize(Decimal("0.0001"))
    return 1, amount, f"{description} ({item.quantity} × ${item.unit_price})"


def aliquot_from_rate(rate: Decimal) -> IvaAliquot:
    return _ALIQUOT_BY_RATE.get(rate.quantize(Decimal("0.01")), IvaAliquot.exempt)


def voucher_type_enum(letter: str) -> VoucherType:
    # `parsed.voucher_type` es "A"/"B"/"C" (o NC…), y VoucherType(letter) espera ese
    # string exacto — es su `_value_`. Un valor inesperado revienta acá, que es donde
    # debe: es una condición de is_verified que ya se validó.
    return VoucherType(letter)


def _skip(reason: str, path: Path) -> None:
    logger.info("SALTAR %s — %s", path.name, reason)


def import_one(
    db: Session,
    base_dir: Path,
    pdf_path: Path,
    kind: InvoiceType,
    entity: Entity,
    fiscal_identities: dict[str, FiscalIdentity],
    dry_run: bool,
    result: ImportResult,
) -> None:
    """Importa un PDF. Nunca lanza — todo error se cuenta y se anota, para que un archivo
    dañado no corte un lote de miles."""
    result.total += 1
    external_id = external_id_for(base_dir, pdf_path)

    already = db.execute(
        select(Invoice.id).where(
            Invoice.external_source == SOURCE, Invoice.external_id == external_id
        )
    ).scalar_one_or_none()
    if already is not None:
        result.skipped_existing += 1
        logger.debug("ya cargado: %s", pdf_path.name)
        return

    try:
        content = pdf_path.read_bytes()
    except OSError as e:
        result.skipped_other += 1
        _skip(f"no se pudo leer el archivo: {e}", pdf_path)
        return

    parsed = parse_invoice_file(pdf_path.name, content)
    if not is_verified(parsed):
        result.skipped_unverified += 1
        _skip(
            f"no verifica (letter={parsed.voucher_type} pos={parsed.pos} num={parsed.number} "
            f"cuit={parsed.supplier_cuit} cae={parsed.cae} total={parsed.total} "
            f"gap={lines_gap(parsed)} gap_totales={lines_gap(parsed, use_totals=True)})",
            pdf_path,
        )
        return

    # A esta altura el header está completo: parsed.voucher_type, pos, number, date,
    # supplier_cuit y cae son no-None (lo garantiza is_verified). Los asserts son para
    # convencer a mypy — is_verified ya rechazó cualquier None.
    assert parsed.voucher_type is not None  # noqa: S101
    assert parsed.date is not None  # noqa: S101
    assert parsed.supplier_cuit is not None  # noqa: S101

    # El parser puede devolver el CUIT con guiones ("20-18281067-4"), y `Contact.tax_id`
    # se guarda solo con dígitos (el schema Pydantic normaliza así en el resto de la app).
    # Se normaliza acá para que la comparación con el prefijo del filename, la búsqueda
    # de identidad fiscal y la de contacto sean todas contra la misma forma.
    supplier_tax_id = digits_only(parsed.supplier_cuit)

    fiscal_identity_id: uuid.UUID | None = None
    if kind is InvoiceType.sale:
        # En ventas, el emisor es una de las dos identidades fiscales de InSoft. Chequeo
        # cruzado contra el prefijo del filename: si no coinciden, el archivo está en el
        # directorio equivocado (o el parser leyó mal el CUIT) y no se carga.
        prefix = tax_id_from_filename(pdf_path)
        if prefix is not None and prefix != supplier_tax_id:
            result.skipped_other += 1
            _skip(
                f"el CUIT del emisor ({supplier_tax_id}) no coincide con el prefijo "
                f"del nombre del archivo ({prefix})",
                pdf_path,
            )
            return
        fiscal_identity = fiscal_identities.get(supplier_tax_id)
        if fiscal_identity is None:
            result.skipped_other += 1
            _skip(
                f"el CUIT emisor ({supplier_tax_id}) no está entre las identidades "
                f"fiscales cargadas ({sorted(fiscal_identities)})",
                pdf_path,
            )
            return
        fiscal_identity_id = fiscal_identity.id

    contact = resolve_contact(
        db,
        tax_id=supplier_tax_id,
        name=parsed.supplier_name,
        condicion=parsed.supplier_condicion_iva,
        is_supplier=kind is InvoiceType.purchase,
    )

    voucher = voucher_type_enum(parsed.voucher_type)
    existing = find_existing_formal_invoice(
        db,
        invoice_type=kind,
        fiscal_identity_id=fiscal_identity_id,
        contact_id=contact.id,
        voucher_type=voucher,
        pos=parsed.pos,
        number=parsed.number,
    )
    if existing is not None:
        # El comprobante ya está en la base (cargado a mano desde la UI, por FactuMov, o
        # por una corrida previa con otro `external_id`). No lo tocamos — nada de las
        # líneas, ni las fechas, ni el estado —; sólo le agregamos el PDF **si no tiene
        # ninguno adjunto**, porque re-adjuntar manualmente lo que el script ya tiene en
        # la mano es trabajo inútil para el operador.
        result.skipped_duplicate_formal += 1
        if existing.attachments:
            logger.info(
                "SALTAR %s — ya existe (invoice %s), con adjunto propio",
                pdf_path.name,
                existing.id,
            )
            return
        if dry_run:
            logger.info(
                "SALTAR (dry-run) %s — ya existe (invoice %s), SE LE ADJUNTARÍA el PDF",
                pdf_path.name,
                existing.id,
            )
            result.attached_to_existing += 1
            return
        attachment_service.save(db, existing, pdf_path.name, content, "application/pdf")
        db.flush()
        result.attached_to_existing += 1
        logger.info(
            "SALTAR %s — ya existe (invoice %s), PDF adjuntado",
            pdf_path.name,
            existing.id,
        )
        return

    invoice_data = InvoiceCreate(
        invoice_type=kind,
        entity_id=entity.id,
        fiscal_identity_id=fiscal_identity_id,
        contact_id=contact.id,
        date=parsed.date,
        formal=True,
        tax_only=False,
        voucher_type=voucher,
        pos=parsed.pos,
        number=parsed.number,
        # El histórico ya ocurrió: el comprobante está autorizado (tiene CAE), confirmado
        # (validado y congelado) y la mercadería ya se movió. `paid` queda en False:
        # marcar cobros/pagos por lote es una decisión aparte, y hoy la app lo tiene en la
        # pantalla del comprobante.
        confirmed=True,
        authorized=True,
        paid=False,
        fulfilled_at=parsed.date,
        cae=parsed.cae,
    )

    items = lines_to_use(parsed)
    if not items:
        result.skipped_other += 1
        _skip("verificó pero no hay ítems para cargar (esto no debería pasar)", pdf_path)
        return

    if dry_run:
        result.imported += 1
        logger.info(
            "OK (dry-run) %s → %s %s %d-%d $%s (%d líneas)",
            pdf_path.name,
            kind.value,
            parsed.voucher_type,
            parsed.pos,
            parsed.number,
            parsed.total,
            len(items),
        )
        return

    invoice = invoice_crud.create(db, invoice_data)
    # `create` no setea external_*: se hace después (igual que en services/issued_invoice.py).
    invoice.external_source = SOURCE
    invoice.external_id = external_id

    for item in items:
        quantity, unit_price, description = to_int_quantity(item)
        invoice_line_crud.create(
            db,
            InvoiceLineCreate(
                invoice_id=invoice.id,
                description=description[:255],
                quantity=quantity,
                unit_price=unit_price,
                iva_aliquot=aliquot_from_rate(item.iva_rate),
            ),
        )

    attachment_service.save(db, invoice, pdf_path.name, content, "application/pdf")

    db.flush()
    result.imported += 1
    logger.info(
        "OK %s → %s %s %d-%d $%s (%d líneas)",
        pdf_path.name,
        kind.value,
        parsed.voucher_type,
        parsed.pos,
        parsed.number,
        parsed.total,
        len(items),
    )


def iter_pdfs(base_dir: Path) -> Iterable[Path]:
    # Un solo recorrido, comparando la extensión en minúsculas. Antes eran dos `rglob`, uno
    # por "*.pdf" y otro por "*.PDF": en Linux son patrones distintos, pero en Windows el
    # sistema de archivos no distingue mayúsculas y los dos devolvían el mismo archivo, así
    # que cada PDF se procesaba dos veces. Y un ".Pdf" no lo encontraba ninguno de los dos.
    yield from sorted(p for p in base_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def run(base_dir: Path, kind: InvoiceType, commit: bool) -> ImportResult:
    result = ImportResult()
    with SessionLocal() as db:
        entity = resolve_entity(db)
        fiscal_identities = resolve_fiscal_identities(db)
        for pdf_path in iter_pdfs(base_dir):
            import_one(
                db,
                base_dir=base_dir,
                pdf_path=pdf_path,
                kind=kind,
                entity=entity,
                fiscal_identities=fiscal_identities,
                dry_run=not commit,
                result=result,
            )
        if commit:
            db.commit()
        else:
            db.rollback()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("directory", type=Path, help="Carpeta a recorrer recursivamente")
    parser.add_argument(
        "--kind",
        required=True,
        choices=[k.value for k in InvoiceType],
        help="purchase = compras, sale = ventas",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persistir de verdad. Por defecto sólo se lista lo que se haría (dry-run).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    if not args.directory.is_dir():
        raise SystemExit(f"{args.directory}: no es una carpeta")
    kind = InvoiceType(args.kind)
    logger.info(
        "%s desde %s (%s)",
        "IMPORTANDO" if args.commit else "DRY-RUN",
        args.directory,
        kind.value,
    )
    result = run(args.directory, kind, args.commit)
    result.log_summary()
    return 0 if result.total == 0 or result.imported > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
