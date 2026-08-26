"""El select de letras del encabezado no mezcla NC con comprobantes comunes.

Una NC nace de create_credit_note con su comprobante original; ofrecer las letras
NC en un comprobante comun (o en el alta) es la unica forma de llegar por UI a una
NC sin original. Los casos se prueban sobre el HTML que sale del partial, que es
compartido por el alta y por la edicion del encabezado.
"""

import re

from balance360.enums import (
    CREDIT_NOTE_VOUCHERS,
    Concepto,
    InvoiceType,
    VoucherType,
)
from balance360.web.templating import templates
from tests import factories

PLAIN_LETTERS = ["A", "B", "C"]
NC_LETTERS = ["NCA", "NCB", "NCC"]


def _render_header(invoice=None):
    template = templates.env.get_template("invoices/partials/_header_fields.html")
    return template.render(
        invoice=invoice,
        entities=[],
        contacts=[],
        categories=[],
        fiscal_identities=[],
        selected_fiscal_identity_id=None,
        invoice_type=InvoiceType,
        voucher_type=VoucherType,
        concepto=Concepto,
    )


def _offered_letters(html):
    """Los value= de las opciones del select de letras, sin el placeholder."""
    select = re.search(r'<select name="voucher_type".*?</select>', html, re.S)
    assert select, "no se encontro el select de letras en el partial"
    return [value for value in re.findall(r'<option value="([^"]*)"', select.group(0)) if value]


def test_credit_note_letters_partition_voucher_types():
    assert [vt.value for vt in CREDIT_NOTE_VOUCHERS] == NC_LETTERS
    assert [vt.value for vt in VoucherType if vt.is_credit_note] == NC_LETTERS
    assert [vt.value for vt in VoucherType if not vt.is_credit_note] == PLAIN_LETTERS


def test_new_invoice_form_offers_no_credit_note_letters():
    assert _offered_letters(_render_header()) == PLAIN_LETTERS


def test_plain_invoice_header_offers_no_credit_note_letters(db):
    invoice = factories.make_invoice(db, voucher_type=VoucherType.A)

    assert _offered_letters(_render_header(invoice)) == PLAIN_LETTERS


def test_credit_note_header_offers_only_credit_note_letters(db):
    nc = factories.make_invoice(db, voucher_type=VoucherType.NCA)

    assert nc.is_nc
    assert _offered_letters(_render_header(nc)) == NC_LETTERS


def test_informal_invoice_offers_no_credit_note_letters(db):
    """Sin letra no hay is_nc; el select existe igual aunque quede oculto."""
    invoice = factories.make_invoice(db, formal=False, voucher_type=None)
    invoice.voucher_type = None

    assert _offered_letters(_render_header(invoice)) == PLAIN_LETTERS
