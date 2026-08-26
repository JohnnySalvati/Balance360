import base64
import json

import segno

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

    Lleva letra, punto de venta y numero para que el destinatario no acumule
    cinco archivos llamados todos 'comprobante.pdf'.
    """
    letter = invoice.voucher_type.value if invoice.voucher_type else "X"
    return f"{letter}-{invoice.pos:05d}-{invoice.number:08d}.pdf"
