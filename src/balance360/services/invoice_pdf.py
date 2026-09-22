import base64
import json
from functools import cache
from pathlib import Path

import segno

from balance360.enums import InvoiceType
from balance360.exceptions import InvoicePrintError, QrValidationError
from balance360.models.invoice import Invoice


def build_qr(invoice: Invoice) -> str:
    if not (invoice.voucher_type and invoice.cae and invoice.fiscal_identity):
        raise QrValidationError("Insuficient data to build QR")

    invoice_dict = {
        "ver": 1,
        "fecha": invoice.date.isoformat(),
        "cuit": int(invoice.fiscal_identity.tax_id or "0"),
        "ptoVta": invoice.pos,
        "tipoCmp": invoice.voucher_type.arca_code,
        "nroCmp": invoice.number,
        "importe": float(invoice.total),
        "moneda": "PES",
        "ctz": 1,
        "tipoDocRec": invoice.contact.doc_type.value,
        "nroDocRec": int(invoice.contact.tax_id or "0"),
        "tipoCodAut": "E",
        "codAut": int(invoice.cae),
    }

    invoice_data = base64.b64encode(json.dumps(invoice_dict).encode()).decode()
    url = "https://www.arca.gob.ar/fe/qr/?p=" + invoice_data

    return segno.make(url).png_data_uri(scale=3)


def render_pdf_bytes(html: str) -> bytes:
    """Convierte a PDF el HTML ya renderizado del comprobante.

    Recibe el HTML y no el Invoice a proposito: renderizar templates es tarea de
    la capa web, y un servicio que importe web/templating.py invierte las capas.
    Aca queda solo el envoltorio de weasyprint, que no depende de nada web.

    El import va adentro de la funcion porque weasyprint carga las librerias GTK
    al importarse: en una maquina sin GTK el import falla, y si estuviera arriba
    se caeria la aplicacion entera al arrancar en vez de solo esta operacion.
    """
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as e:
        raise InvoicePrintError(
            "No se puede generar el PDF: falta weasyprint o sus librerias GTK"
        ) from e

    pdf: bytes = HTML(string=html).write_pdf()
    return pdf


def pdf_filename(invoice: Invoice) -> str:
    """Nombre del archivo adjunto en el mail.

    El formal lleva letra, punto de venta y numero para que el destinatario no
    acumule cinco archivos llamados todos 'comprobante.pdf'. El informal no tiene
    numeracion, asi que se nombra con la fecha y un tramo del id.
    """
    if invoice.voucher_type and invoice.pos and invoice.number:
        return f"{invoice.voucher_type.value}-{invoice.pos:05d}-{invoice.number:08d}.pdf"

    kind = "venta" if invoice.invoice_type == InvoiceType.sale else "compra"
    return f"comprobante-{kind}-{invoice.date:%Y%m%d}-{str(invoice.id)[:8]}.pdf"


@cache
def insoft_logo_data_uri() -> str:
    """El logo de InSoft embebido como data URI, para que entre en el PDF.

    Va embebido y no como `<img src="/static/insoft-logo.svg">` porque
    `render_pdf_bytes` llama a `HTML(string=html)` sin `base_url`: weasyprint no
    tiene contra que resolver una URL relativa y el logo sale vacio, sin error.
    El data URI hace que el HTML sea autosuficiente -- el mismo documento
    imprime igual desde el disco, desde el navegador y adjunto a un mail.

    Cacheado porque el archivo no cambia entre requests y son 4 KB que no hacen
    falta releer en cada impresion.
    """
    svg = (Path(__file__).parent.parent / "static" / "insoft-logo.svg").read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(svg).decode()


def remito_filename(invoice: Invoice) -> str:
    """Nombre del remito, derivado del comprobante que lo origina.

    El remito no tiene numeracion propia -- no es un remito R autorizado por
    ARCA, es la constancia de entrega de esta factura -- asi que se nombra con
    la del comprobante, o con la fecha y el id cuando no hay numeracion.
    """
    if invoice.pos and invoice.number:
        return f"remito-{invoice.pos:05d}-{invoice.number:08d}.pdf"
    return f"remito-{invoice.date:%Y%m%d}-{str(invoice.id)[:8]}.pdf"
