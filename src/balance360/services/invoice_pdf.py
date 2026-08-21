import base64
import json

import segno

from balance360.exceptions import QrValidationError
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
