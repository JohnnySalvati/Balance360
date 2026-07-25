import base64
import json

import segno

from balance360.models.invoice import Invoice
from balance360.services.wsfe import voucher_type_code


def build_qr(invoice: Invoice) -> str:
    assert invoice.voucher_type
    assert invoice.cae
    assert invoice.fiscal_identity

    invoice_dict = {
        "ver": 1,
        "fecha": invoice.date.isoformat(),
        "cuit": int(invoice.fiscal_identity.tax_id or "0"),
        "ptoVta": invoice.pos,
        "tipoCmp": voucher_type_code[invoice.voucher_type],
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
