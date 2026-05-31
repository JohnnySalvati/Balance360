"""
Parser for ARCA-valid invoice PDFs.
Returns a ParsedInvoice dataclass; missing fields are None.
Handles multiple layout styles from different billing software.

Item extraction uses a layout registry: each known vendor layout is
identified by its table header (signature) and parsed with a dedicated
row pattern. Adding a new vendor means adding one Layout entry.
"""
from __future__ import annotations
import re
import datetime
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


@dataclass
class ParsedInvoiceLine:
    description: str
    quantity: Decimal
    unit_price: Decimal
    iva_rate: Decimal


@dataclass
class ParsedInvoice:
    voucher_type: str | None
    pos: int | None
    number: int | None
    date: datetime.date | None
    supplier_cuit: str | None
    supplier_name: str | None
    supplier_condicion_iva: str | None
    cae: str | None
    lines: list[ParsedInvoiceLine] = field(default_factory=list)
    # True when the PDF has no extractable text (scanned image) or no known
    # item layout matched; the UI should let the user load items manually.
    needs_manual_items: bool = False


def _parse_date(s: str) -> datetime.date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _to_decimal(s: str|None) -> Decimal | None:
    """Parse a number string in either AR (1.234,56) or US (1,234.56) format.

    The decimal separator is the rightmost '.' or ',' in the token; every
    other separator is treated as a thousands grouping and removed. This
    avoids corrupting US-formatted numbers (the old code assumed AR always).
    """
    if s is None:
        return None
    cleaned = re.sub(r"[^\d.,]", "", s.strip())   # drop $, %, spaces, letters
    if not cleaned:
        return None
    last_dot = cleaned.rfind(".")
    last_comma = cleaned.rfind(",")
    dec_pos = max(last_dot, last_comma)
    if dec_pos == -1:                              # integer, no separators
        digits, frac = cleaned, ""
    else:
        digits = re.sub(r"[.,]", "", cleaned[:dec_pos])
        frac = cleaned[dec_pos + 1:]
    try:
        return Decimal(f"{digits}.{frac}" if frac else digits)
    except InvalidOperation:
        return None


def _normalize_cuit(s: str) -> str:
    digits = re.sub(r'\D', '', s)
    if len(digits) == 11:
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"
    return s


# --------------------------------------------------------------------------
# Header field extraction (unchanged logic, kept as-is)
# --------------------------------------------------------------------------
def _extract_voucher_type(lines: list, text: str) -> str | None:
    for line in lines[:5]:
        if re.match(r'^[A-C]$', line.strip()):
            return line.strip()
    m = re.search(r'^FACTURA\s*\n([A-C])\s+\d{4}-\d+', text, re.MULTILINE)
    if m:
        return m.group(1).upper()
    m = re.search(r'\b([A-C])\s+Nro\s*:', text[:400], re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(r'^([A-C])\s+Fecha', text, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(r'\bFACTURA\b[^\n]*\n[^\n]*\b([A-C])\s*$', text[:400], re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def _extract_pos_number(lines: list, text: str):
    m = re.search(r'Punto de Venta[:\s]+0*(\d+)\s+Comp\.?\s*Nro[:\s]+0*(\d+)', text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'FACTURA\s+0*(\d+)-0*(\d+)', text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'^FACTURA\s*\n[A-C]\s+0*(\d{1,4})-0*(\d+)', text, re.MULTILINE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'Nro[:\s]+[A-C]?-?0*(\d{1,4})[-\s]+0*(\d{4,8})\b', text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'[Ff]actura\s+[A-C]?\s*0*(\d{1,4})-0*(\d{5,8})\b', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _extract_date(text: str) -> datetime.date | None:
    m = re.search(r'Fecha\s+(?:de\s+)?[Ee]misi[oó]n[:\s]+(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
    if m:
        return _parse_date(m.group(1))
    m = re.search(r'Fecha[:\s]+(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
    if m:
        return _parse_date(m.group(1))
    for match in re.finditer(r'\b(\d{1,2}/\d{1,2}/20\d{2})\b', text):
        d = _parse_date(match.group(1))
        if d and d.year >= 2020:
            return d
    return None


# Air/NVX invoices ("FACTURA\nA 0047-…"): the supplier (Venex/NVX) is printed
# only in the logo image, so the text layer carries the BUYER's data. We must
# not return the buyer as the supplier — leave it for manual selection.
_AIR_SIGNATURE = re.compile(r'^FACTURA\s*\n[A-C]\s+\d{4}-\d+', re.MULTILINE)


def _extract_supplier_cuit(lines: list, text: str) -> str | None:
    if _AIR_SIGNATURE.search(text):
        return None
    buyer_pos = text.find("Apellido y Nombre")
    emisor_zone = text[:buyer_pos] if buyer_pos > 0 else text
    m = re.search(r'Cuit\s+Nro\.?[:\s]+(\d{2}-\d{7,8}-\d)', emisor_zone, re.IGNORECASE)
    if m:
        return _normalize_cuit(m.group(1))
    m = re.search(r'C\.?U\.?I\.?T\.?[:\s]+(\d{2}-\d{7,8}-\d)', emisor_zone, re.IGNORECASE)
    if m:
        return _normalize_cuit(m.group(1))
    m = re.search(r'CUIT[:\s]+(\d{11})', emisor_zone, re.IGNORECASE)
    if m:
        return _normalize_cuit(m.group(1))
    return None


_SKIP = re.compile(
    r'^(ORIGINAL|FACTURA|COD[.:\s]|Nro[:\s]|Código|Punto de Venta|Razón Social|Domicilio|Ingresos|'
    r'Condición|CUIT|C\.U\.I\.T|I\.V\.A\.|IVA|Fecha|Inicio|Tel[.:/]|Fax|SR\.|CONCEPTO|'
    r'Detalle|IIBB|Inscripta|Original)',
    re.IGNORECASE
)
_JUNK = re.compile(r'HOJA\s+\d+/\d+|^\(|^Av\.|^Gral\.|^\d|^[A-C]\s+\d{4}-\d+')


def _clean_line(line: str) -> str:
    return re.sub(r'\s+HOJA\s+\d+/\d+.*$', '', line).strip()


def _extract_supplier_name(lines: list, text: str) -> str | None:
    if _AIR_SIGNATURE.search(text):
        return None
    m = re.search(r'^De:\s+(.+?)(?:\s+FACTURA)?\s*$', text, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    buyer_pos = text.find("Apellido y Nombre")
    emisor_zone = text[:buyer_pos] if buyer_pos > 0 else text[:600]
    m = re.search(r'Razón Social[:\s]+(.+?)\s+Fecha', emisor_zone, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    for line in lines[:10]:
        cleaned = _clean_line(line)
        if cleaned and not _SKIP.match(cleaned) and not _JUNK.search(cleaned) and len(cleaned) > 3:
            return cleaned
    return None


def _extract_condicion_iva(text: str, voucher_type: str | None) -> str | None:
    if voucher_type == "C":
        return "MONOTRIBUTO"
    m = re.search(
        r'(Responsable\s+Monotributo|Monotributo|IVA\s+Responsable|'
        r'Responsable\s+Inscripto|Sujeto\s+Exento|Exento)',
        text, re.IGNORECASE
    )
    if not m:
        return None
    raw = m.group(1).upper()
    if "MONO" in raw:
        return "MONOTRIBUTO"
    if "EXENTO" in raw:
        return "EXENTO"
    return "INSCRIPTO"


# --------------------------------------------------------------------------
# Item layout registry
# --------------------------------------------------------------------------
_DEFAULT_IVA: dict = {"A": Decimal("21"), "B": Decimal("21"), "C": Decimal("0")}

# A monetary token: digits with at least one decimal separator (1.234,56 / 1,234.56 / 12345.67)
_MONEY = re.compile(r"\d[.,]\d")

# Lines that mark the end of the item zone (totals / footer).
_TERMINATOR = re.compile(
    r"^\s*("
    r"Importe\b|Subtotal\b|SUBTOTAL\b|SUMA\b|Neto\b|Son\b|SON\b|TOTAL\b|"
    r"PERCEPCION\b|Per\b|Per\.|Régimen\b|Observaciones\b|Detalle IVA|"
    r"Cantidad total|Condición de venta|CAE\b|C\.A\.E|IVA\s+\d|Iva\s+Insc|"
    r"Importe Neto|Comprobante|147\b|TEL\b|Atendio|Cuatro|Un\s+millon"
    r")",
    re.IGNORECASE,
)


@dataclass
class Layout:
    name: str
    signature: re.Pattern   # matches the table header line
    row: re.Pattern         # matches a single item row (named groups)
    wrap: str | None = None  # 'append' (continuation below) | 'prepend' (above) | None
    skip_zero: bool = False  # drop rows whose price is 0 (combo sub-items)


# Number tokens may be AR or US format; _to_decimal sorts it out.
N = r"[\d.,]+"

LAYOUTS: list[Layout] = [
    # 1. ARCA standard (SOLANA, etc.): desc qty 'unidades' price bonif subtotal IVA% total
    Layout(
        name="arca",
        signature=re.compile(r"Código\s+Producto\s*/\s*Servicio\s+Cantidad\s+U\.?\s*medida", re.I),
        row=re.compile(
            rf"^(?P<desc>.+?)\s+(?P<qty>\d+,\d+)\s+unidades\s+(?P<price>{N})\s+{N}\s+{N}\s+(?P<iva>\d+)%\s+{N}\s*$"
        ),
    ),
    # 2. Air / NVX: qty code desc GI/GP iva impint price subtotal
    Layout(
        name="air_nvx",
        signature=re.compile(r"Cant\.\s+Código\s+Descripción.*Precio.*Subtotal", re.I),
        row=re.compile(
            rf"^(?P<qty>\d+)\s+(?P<code>\S+)\s+(?P<desc>.+?)\s*\d+/\d+\s+(?P<iva>\d+,\d+)\s+{N}\s+(?P<price>{N})\s+{N}\s*$"
        ),
    ),
    # 3. Venex: qty [- ]desc (iva%) $ price [$ subtotal]
    Layout(
        name="venex",
        signature=re.compile(r"Cant\.?Descripción.*Unitario.*Subtotal", re.I),
        row=re.compile(
            rf"^(?P<qty>\d+)\s+-?\s*(?P<desc>.+?)\s+\((?P<iva>\d+[,.]\d+)%\)\s+\$\s*(?P<price>{N})(?:\s+\$\s*{N})?\s*$"
        ),
        skip_zero=True,
    ),
    # 4. Memos: qty code desc price iva % bonif % importe
    Layout(
        name="memos",
        signature=re.compile(r"Cantidad\s+Código\s+Descripción\s+Precio\s+unitario\s+IVA\s+Bonif", re.I),
        row=re.compile(
            rf"^(?P<qty>\d+)\s+(?P<code>\S+)\s+(?P<desc>.+?)\s+(?P<price>{N})\s+(?P<iva>\d+,\d+)\s*%\s+{N}\s*%\s+{N}\s*$"
        ),
        wrap="append",
    ),
    # 5. ZTECNO: qty code desc iva price dto importe
    Layout(
        name="ztecno",
        signature=re.compile(r"CANTIDAD\s+CODIGO\s+DESCRIPCION\s+%?\s*IVA\s+PRECIO\s+%?\s*Dto\s+IMPORTE", re.I),
        row=re.compile(
            rf"^(?P<qty>\d+)\s+(?P<code>\S+)\s+(?P<desc>.+?)\s+(?P<iva>\d+,\d+)\s+(?P<price>{N})\s+{N}\s+{N}\s*$"
        ),
        wrap="append",
    ),
    # 6. Gaming-City: code qty desc $ price iva % bonif % $ importe
    Layout(
        name="gamingcity",
        signature=re.compile(r"Código\s+Cant\.\s+Producto\s+Precio\s+IVA\s+Bonif", re.I),
        row=re.compile(
            rf"^(?P<code>\S+)\s+(?P<qty>\d+)\s+(?P<desc>.+?)\s+\$\s*(?P<price>{N})\s+(?P<iva>\d+(?:\.\d+)?)\s*%\s+{N}\s*%\s+\$\s*{N}\s*$"
        ),
    ),
    # 7. FullHard: unid desc qty bonif price iva% ivaImp importe (desc may wrap above)
    Layout(
        name="fullhard",
        signature=re.compile(r"Unid\.\s+Descripción\s+Cantidad\s+Bonif.*Precio.*Importe", re.I),
        row=re.compile(
            rf"^(?P<desc>.*?)\s*(?P<qty>\d+\.\d+)\s+{N}\s+(?P<price>{N})\s+(?P<iva>\d+(?:\.\d+)?)%\s+{N}\s+{N}\s*$"
        ),
        wrap="prepend",
    ),
    # 8. Giannantonio: code desc qty price importe (IVA from voucher default)
    Layout(
        name="giannantonio",
        signature=re.compile(r"CODIGO\s+DESCRIPCION\s+CANTIDAD\s+P\.?\s*UNITARIO\s+IMPORTE", re.I),
        row=re.compile(
            rf"^(?P<code>\S+)\s+(?P<desc>.+?)\s+(?P<qty>\d+\.\d+)\s+(?P<price>{N})\s+(?P<importe>{N})\s*$"
        ),
    ),
]


def _detect_layout(lines: list) -> tuple[Layout | None, int]:
    """Return (layout, header_index) for the first matching table header."""
    for idx, line in enumerate(lines):
        for layout in LAYOUTS:
            if layout.signature.search(line):
                return layout, idx
    return None, -1


def _make_line(layout: Layout, gd: dict, default_iva: Decimal) -> ParsedInvoiceLine | None:
    qty = _to_decimal(gd.get("qty", "1"))
    price = _to_decimal(gd.get("price"))
    if qty is None or price is None:
        return None
    if layout.skip_zero and price == 0:
        return None
    iva = _to_decimal(gd["iva"]) if gd.get("iva") else default_iva
    if iva is None:
        iva = default_iva
    desc = re.sub(r"\s+", " ", gd.get("desc", "").strip())
    return ParsedInvoiceLine(desc, qty, price, iva)


def _extract_items(lines: list, voucher_type: str | None) -> list:
    layout, hdr = _detect_layout(lines)
    if layout is None:
        return []
    default_iva = _DEFAULT_IVA.get(voucher_type or "A", Decimal("21"))
    result: list[ParsedInvoiceLine] = []
    pending = ""  # buffered description text (for 'prepend' layouts)

    for line in lines[hdr + 1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if _TERMINATOR.match(stripped):
            break
        m = layout.row.match(line)
        if m:
            gd = m.groupdict()
            if layout.wrap == "prepend" and pending:
                gd["desc"] = f"{pending} {gd.get('desc', '')}".strip()
                pending = ""
            item = _make_line(layout, gd, default_iva)
            if item:
                result.append(item)
            continue
        # Non-row line inside the item zone.
        if layout.wrap == "prepend":
            # Descriptions wrap ABOVE the numeric row and may contain numbers
            # (e.g. '15.6"', '512GB'); buffer the whole text line.
            pending = f"{pending} {stripped}".strip() if pending else stripped
            continue
        if layout.wrap == "append" and result:
            # Continuation BELOW the row. Skip metadata lines (codes, ids,
            # labels) which carry ':' or '#'; keep plain text fragments.
            if _MONEY.search(stripped) or ":" in stripped or "#" in stripped:
                continue
            result[-1].description = re.sub(
                r"\s+", " ", f"{result[-1].description} {stripped}".strip()
            )
    return result


def parse_invoice_pdf(file_bytes: bytes) -> ParsedInvoice:
    import pdfplumber
    import io
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        # Corrupt or scanned PDF that pdfplumber can't read -> manual entry.
        text = ""
    lines = text.split("\n")

    voucher_type = _extract_voucher_type(lines, text)
    pos, number = _extract_pos_number(lines, text)
    date = _extract_date(text)
    supplier_cuit = _extract_supplier_cuit(lines, text)
    supplier_name = _extract_supplier_name(lines, text)
    supplier_condicion_iva = _extract_condicion_iva(text, voucher_type)

    cae = None
    m = re.search(r'C\.?A\.?E\.?\s*(?:N[°o]?\.?)?[:\s#]+(\d{14})', text)
    if m:
        cae = m.group(1)

    items = _extract_items(lines, voucher_type)
    needs_manual_items = not items

    return ParsedInvoice(
        voucher_type=voucher_type,
        pos=pos,
        number=number,
        date=date,
        supplier_cuit=supplier_cuit,
        supplier_name=supplier_name,
        supplier_condicion_iva=supplier_condicion_iva,
        cae=cae,
        lines=items,
        needs_manual_items=needs_manual_items,
    )
