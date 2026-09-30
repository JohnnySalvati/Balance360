"""
Parser for ARCA-valid invoice PDFs.
Returns a ParsedInvoice dataclass; missing fields are None.
Handles multiple layout styles from different billing software.

Item extraction uses a layout registry: each known vendor layout is
identified by its table header (signature) and parsed with a dedicated
row pattern. Adding a new vendor means adding one Layout entry.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from balance360.models.money import money


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
    # Lo que el propio PDF declara como total, y lo que suman sus tributos (percepciones).
    # No reemplazan a `lines`: sirven para **verificar** que lo leído cierra, que es la única
    # forma de enterarse de que un layout nuevo leyó mal una columna sin mirar cada factura.
    total: Decimal | None = None
    tributes_total: Decimal = Decimal(0)
    # Líneas derivadas de los totales (neto e IVA por alícuota) cuando ningún layout de
    # ítems reconoció la tabla. Son verdaderas pero sin detalle de producto: sirven para
    # cargar el histórico sin perder un peso, no para la pantalla de alta, que sigue
    # mirando `lines` y `needs_manual_items` como antes.
    totals_lines: list[ParsedInvoiceLine] = field(default_factory=list)
    # True when the PDF has no extractable text (scanned image) or no known
    # item layout matched; the UI should let the user load items manually.
    needs_manual_items: bool = False
    # How the text was obtained: "text" (PDF text layer) or "ocr" (scan). An OCR read is
    # never trusted on its own: see `is_verified`.
    source: str = "text"


def _parse_date(s: str) -> datetime.date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _to_decimal(s: str | None) -> Decimal | None:
    """Parse a number string in either AR (1.234,56) or US (1,234.56) format.

    The decimal separator is the rightmost '.' or ',' in the token; every
    other separator is treated as a thousands grouping and removed. This
    avoids corrupting US-formatted numbers (the old code assumed AR always).
    """
    if s is None:
        return None
    raw = s.strip()
    # Keep the sign: "-8.977,04" (leading, e.g. discount rows) or
    # "8.977,04-" (trailing, printed by some ERPs).
    negative = bool(re.match(r"^[^\d]*-", raw)) or raw.endswith("-")
    cleaned = re.sub(r"[^\d.,]", "", raw)  # drop $, %, spaces, letters
    if not cleaned:
        return None
    last_dot = cleaned.rfind(".")
    last_comma = cleaned.rfind(",")
    dec_pos = max(last_dot, last_comma)
    if dec_pos == -1:  # integer, no separators
        digits, frac = cleaned, ""
    else:
        digits = re.sub(r"[.,]", "", cleaned[:dec_pos])
        frac = cleaned[dec_pos + 1 :]
    try:
        value = Decimal(f"{digits}.{frac}" if frac else digits)
    except InvalidOperation:
        return None
    return -value if negative else value


def _normalize_cuit(s: str) -> str:
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11:
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"
    return s


# --------------------------------------------------------------------------
# Header field extraction (unchanged logic, kept as-is)
# --------------------------------------------------------------------------
def _extract_voucher_type(lines: list, text: str) -> str | None:
    for line in lines[:5]:
        if re.match(r"^[A-C]$", line.strip()):
            return line.strip()
    m = re.search(r"^FACTURA\s*\n([A-C])\s+\d{4}-\d+", text, re.MULTILINE)
    if m:
        return m.group(1).upper()
    # La letra suelta junto a la palabra: "A FACTURA" (Avantecno, INCOT), "A Factura" (Segal).
    # Solo en el encabezado, y con la palabra pegada: una "A" cualquiera del texto no cuenta.
    m = re.search(r"^([A-C])\s+Factura\b", text[:300], re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Fantino imprime la marca "Original" partida por la letra: "Orig A inal Factura".
    m = re.search(r"\bOrig\s+([A-C])\s+inal\b", text[:300])
    if m:
        return m.group(1).upper()
    m = re.search(r"\bFC\s+Electr\.?\s+([A-C])\b", text[:600], re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Polytech: "Ciudad de Bs. As. A 00387105" (la letra y el número, en el renglón de abajo).
    m = re.search(r"Factura:\s*\d{1,4}-\s*\n[^\n]*?\b([A-C])\s+\d{6,8}\b", text[:400])
    if m:
        return m.group(1).upper()
    m = re.search(r"\b([A-C])\s+Nro\s*:", text[:400], re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(r"^([A-C])\s+Fecha", text, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(
        r"\bFACTURA\b[^\n]*\n[^\n]*\b([A-C])\s*$", text[:400], re.MULTILINE | re.IGNORECASE
    )
    if m:
        return m.group(1).upper()
    # Last resort: AFIP voucher code under a "Cod." box (Dux Software).
    # pdfplumber may keep it inline ("Cod.\n001") or push the digits to the
    # end of the NEXT line ("Cod. FECHA: ...\nTEL: ... 001"). Case-sensitive
    # on purpose: other vendors print uppercase "COD." item labels.
    m = re.search(r"\bCod\.\s*0*(\d{1,3})\s*$", text, re.MULTILINE)
    if not m:
        m = re.search(r"\bCod\.[^\n]*\n[^\n]*?\b0*(\d{1,3})\s*$", text, re.MULTILINE)
    if m:
        return _AFIP_VOUCHER_LETTER.get(int(m.group(1)))
    # ARCA's own portal layout: a whole line "COD. 011" under the letter box. OCR reads the
    # dot as a comma ("COD, 011") and the scan has no letter line the rules above can use.
    # Last of all, and only when the code maps to a known voucher, so that other vendors'
    # "COD." item labels can't produce a wrong letter.
    m = re.search(r"^COD[.,:]?\s*0*(\d{1,3})\s*$", text, re.MULTILINE)
    if m:
        return _AFIP_VOUCHER_LETTER.get(int(m.group(1)))
    return None


def _extract_pos_number(lines: list, text: str):
    # Polytech parte el número en dos renglones: "... Factura: 0003-" y, abajo, "A 00387105".
    # Va primero porque otro patrón levanta "901-971132" (la jurisdicción y el IIBB) y **no da
    # error**: devuelve un número que parece válido.
    m = re.search(r"Factura:\s*0*(\d{1,4})-\s*\n[^\n]*?\b[A-C]\s+0*(\d{6,8})\b", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"Punto de Venta[:\s]+0*(\d+)\s+Comp\.?\s*Nro[:\s]+0*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"Punto de Venta:?\s*0*(\d+)\s+Nro\.?\s*Comp\.?:?\s*0*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"FACTURA\s+0*(\d+)\s*-\s*0*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"^FACTURA\s*\n[A-C]\s+0*(\d{1,4})-0*(\d+)", text, re.MULTILINE)
    if m:
        return int(m.group(1)), int(m.group(2))
    # "Nº 00002-00006657" (Dux) / "Nº A00005-00024903" (ssd-ml style).
    m = re.search(r"\bN[º°o]\.?:?\s*[A-C]?\s*0*(\d{1,5})\s*-\s*0*(\d+)\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"Nro\.?[:\s]+[A-C]?-?0*(\d{1,4})[-\s]+0*(\d{4,8})\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"[Ff]actura\s+[A-C]?\s*0*(\d{1,4})-0*(\d{5,8})\b", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Último recurso: el número pelado en una línea propia ("0003-00019753", "00007-00006083"),
    # solo en el encabezado — más abajo hay números de CAE, remitos y pedidos con la misma forma.
    m = re.search(r"^0*(\d{1,5})-0*(\d{8})\s*$", text[:400], re.MULTILINE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


_EN_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}


def _extract_date(text: str) -> datetime.date | None:
    # "FECHA: May 15, 2025" (Polytech): el mes en inglés no lo toma ningún otro patrón, y el
    # último recurso de abajo levantaría la primera fecha dd/mm/aaaa del PDF, que en una
    # factura es la de **inicio de actividades del proveedor** (19/04/1991 o similar).
    m = re.search(r"Fecha:?\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),\s*(\d{4})", text, re.IGNORECASE)
    if m and m.group(1).lower() in _EN_MONTHS:
        return datetime.date(int(m.group(3)), _EN_MONTHS[m.group(1).lower()], int(m.group(2)))
    m = re.search(
        r"Fecha\s+(?:de\s+)?[Ee]misi[oó]n[:\s]+(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE
    )
    if m:
        return _parse_date(m.group(1))
    m = re.search(r"Fecha[:\s]+(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE)
    if m:
        return _parse_date(m.group(1))
    # "21-01-2025" (Binaghi) y "FECHA:28/08/25" (Todovisión): rotulados como fecha del
    # comprobante, que es lo que los distingue de la fecha de inicio de actividades.
    m = re.search(r"Fecha:?\s*(\d{1,2}[-/]\d{1,2}[-/](?:\d{4}|\d{2}))\b", text, re.IGNORECASE)
    if m:
        return _parse_date(m.group(1).replace("-", "/"))
    m = re.search(r"^(\d{1,2}-\d{1,2}-\d{4})\s*$", text[:300], re.MULTILINE)
    if m:
        return _parse_date(m.group(1).replace("-", "/"))
    for match in re.finditer(r"\b(\d{1,2}/\d{1,2}/20\d{2})\b", text):
        d = _parse_date(match.group(1))
        if d and d.year >= 2020:
            return d
    return None


# ARCA voucher-type code (the "Cod. NNN" box printed by Dux Software and
# similar) -> invoice letter. Unknown codes map to None on purpose: better
# no letter than a wrong one (other vendors print unrelated "COD." lines).
_AFIP_VOUCHER_LETTER = {
    1: "A",
    2: "A",
    3: "A",
    201: "A",
    202: "A",
    203: "A",
    6: "B",
    7: "B",
    8: "B",
    206: "B",
    207: "B",
    208: "B",
    11: "C",
    12: "C",
    13: "C",
    211: "C",
    212: "C",
    213: "C",
}


# Air/NVX invoices ("FACTURA\nA 0047-…"): the supplier is printed only in the logo image,
# so the text layer carries the BUYER's data. We must not return the buyer as the supplier.
_AIR_SIGNATURE = re.compile(r"^FACTURA\s*\n[A-C]\s+\d{4}-\d+", re.MULTILINE)


@dataclass(frozen=True)
class KnownSupplier:
    name: str
    cuit: str


# Proveedores cuyo encabezado no se puede leer del texto. Se reconocen por la **plantilla**
# (firma + punto de venta), nunca por el nombre de archivo ni por lo que diga la descripción.
#
# El CUIT de AIR S.R.L. está leído del logo de la factura (la imagen, no el texto) y verificado
# con el dígito de control. Es el punto de venta 47 de esa plantilla: si otro proveedor usara
# la misma plantilla con otro punto de venta, no matchea y queda para elegir a mano, que es
# mejor que asignarle el CUIT equivocado a una compra.
_AIR_SUPPLIER = KnownSupplier("AIR S.R.L.", "30-57013558-5")
_AIR_POS = 47


def _known_supplier(text: str, pos: int | None) -> KnownSupplier | None:
    if _AIR_SIGNATURE.search(text) and pos == _AIR_POS:
        return _AIR_SUPPLIER
    return None


def _extract_supplier_cuit(lines: list, text: str) -> str | None:
    if _AIR_SIGNATURE.search(text):
        return None
    buyer_pos = text.find("Apellido y Nombre")
    emisor_zone = text[:buyer_pos] if buyer_pos > 0 else text
    m = re.search(r"Cuit\s+Nro\.?[:\s]+(\d{2}-\d{7,8}-\d|\d{11})\b", emisor_zone, re.IGNORECASE)
    if m:
        return _normalize_cuit(m.group(1))
    m = re.search(r"C\.?U\.?I\.?T\.?[:\s]+(\d{2}-\d{7,8}-\d)", emisor_zone, re.IGNORECASE)
    if m:
        return _normalize_cuit(m.group(1))
    m = re.search(r"CUIT[:\s]+(\d{11})", emisor_zone, re.IGNORECASE)
    if m:
        return _normalize_cuit(m.group(1))
    return None


_SKIP = re.compile(
    r"^(ORIGINAL|FACTURA|COD[.:\s]|Nro[:\s]|Código|Punto de Venta|Razón Social|Domicilio|Ingresos|"
    r"Condición|CUIT|C\.U\.I\.T|I\.V\.A\.|IVA|Fecha|Inicio|Tel[.:/]|Fax|SR\.|CONCEPTO|"
    r"Detalle|IIBB|Inscripta|Original)",
    re.IGNORECASE,
)
_JUNK = re.compile(r"HOJA\s+\d+/\d+|^\(|^Av\.|^Gral\.|^\d|^[A-C]\s+\d{4}-\d+")


def _clean_line(line: str) -> str:
    return re.sub(r"\s+HOJA\s+\d+/\d+.*$", "", line).strip()


def _extract_supplier_name(lines: list, text: str) -> str | None:
    if _AIR_SIGNATURE.search(text):
        return None
    m = re.search(r"^De:\s+(.+?)(?:\s+FACTURA)?\s*$", text, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    buyer_pos = text.find("Apellido y Nombre")
    emisor_zone = text[:buyer_pos] if buyer_pos > 0 else text[:600]
    m = re.search(r"Razón Social[:\s]+(.+?)\s+Fecha", emisor_zone, re.IGNORECASE)
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
        r"(Responsable\s+Monotributo|Monotributo|IVA\s+Responsable|"
        r"Responsable\s+Inscripto|Sujeto\s+Exento|Exento)",
        text,
        re.IGNORECASE,
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
    signature: re.Pattern  # matches the table header line
    row: re.Pattern  # matches a single item row (named groups)
    wrap: str | None = None  # 'append' (continuation below) | 'prepend' (above) | None
    skip_zero: bool = False  # drop rows whose price is 0 (combo sub-items)


# Number tokens may be AR or US format; _to_decimal sorts it out.
N = r"[\d.,]+"

LAYOUTS: list[Layout] = [
    # 0. Comprobante del portal de ARCA, letras B y C: no hay columna de IVA (en una B el IVA
    #    viene adentro del precio y en una C no hay). Es el formato de **todo lo que emite el
    #    portal** (punto de venta 2), o sea el de las facturas propias. Va antes que `arca`
    #    porque las dos firmas coinciden en el encabezado y `_detect_layout` se queda con la
    #    primera: el que exige el `Subtotal` al final, sin "Alícuota", es este.
    Layout(
        name="arca_portal_bc",
        signature=re.compile(
            r"Producto\s*/\s*Servicio\s+Cantidad\s+U\.?\s*medida\s+Precio\s+Unit\.?\s+%\s*Bonif"
            r"\s+Imp\.?\s*Bonif\.?\s+Subtotal\s*$",
            re.I,
        ),
        row=re.compile(
            rf"^(?P<desc>.+?)\s+(?P<qty>\d+,\d+)\s+\S+\s+(?P<price>{N})\s+{N}\s+{N}\s+{N}\s*$"
        ),
    ),
    # 1. ARCA standard (SOLANA, etc.): desc qty 'unidades' price bonif subtotal IVA% total
    Layout(
        name="arca",
        signature=re.compile(r"Código\s+Producto\s*/\s*Servicio\s+Cantidad\s+U\.?\s*medida", re.I),
        row=re.compile(
            rf"^(?P<desc>.+?)\s+(?P<qty>\d+,\d+)\s+unidades\s+(?P<price>{N})\s+{N}\s+{N}\s+(?P<iva>\d+(?:,\d+)?)%\s+{N}\s*$"
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
        signature=re.compile(
            r"Cantidad\s+Código\s+Descripción\s+Precio\s+unitario\s+IVA\s+Bonif", re.I
        ),
        row=re.compile(
            rf"^(?P<qty>\d+)\s+(?P<code>\S+)\s+(?P<desc>.+?)\s+(?P<price>{N})\s+(?P<iva>\d+,\d+)\s*%\s+{N}\s*%\s+{N}\s*$"
        ),
        wrap="append",
    ),
    # 5. ZTECNO: qty code desc iva price dto importe
    Layout(
        name="ztecno",
        signature=re.compile(
            r"CANTIDAD\s+CODIGO\s+DESCRIPCION\s+%?\s*IVA\s+PRECIO\s+%?\s*Dto\s+IMPORTE", re.I
        ),
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
    # 9. Dux Software (EVER/EMVI, etc.): code desc qty price subtotal iva% total
    #    Continuation fragments like "(813)" wrap BELOW the row -> append.
    Layout(
        name="dux",
        signature=re.compile(r"Código\s+Descripción\s+Cant\.\s+Precio\s+Uni\.", re.I),
        row=re.compile(
            rf"^(?P<code>\S+)\s+(?P<desc>.+?)\s+(?P<qty>\d+,\d+)\s+(?P<price>{N})\s+{N}\s+(?P<iva>\d+,\d+)\s+{N}\s*$"
        ),
        wrap="append",
    ),
    # 10c. Todovisión: code desc qty iva price total. La alícuota viene en su columna.
    Layout(
        name="todovision",
        signature=re.compile(r"CODIGO\s+DETALLE\s+CANT\s+DESPACHO\s+Porc\.?\s*IVA", re.I),
        row=re.compile(
            rf"^(?P<code>\S+)\s+(?P<desc>.+?)\s+(?P<qty>\d+\.\d+)\s+(?P<iva>\d+\.\d+)\s+(?P<price>{N})\s+{N}\s*$"
        ),
    ),
    # 10a. Dux "ARTÍCULO DETALLE CANTIDAD PRECIO IVA TOTAL": code+desc, qty, price, iva%, total.
    #      Con el código pegado a la descripción (no hay columna aparte), así que todo va en `desc`.
    Layout(
        name="dux_articulo",
        signature=re.compile(r"ART[IÍ]CULO\s+DETALLE\s+CANTIDAD\s+PRECIO\s+IVA\s+TOTAL", re.I),
        row=re.compile(
            rf"^(?P<desc>.+?)\s+(?P<qty>\d+\.\d+)\s+(?P<price>{N})\s+(?P<iva>\d+\.\d+)%\s+{N}\s*$"
        ),
    ),
    # 10b. Avantecno: qty code desc price importe remito. El IVA sale de la letra (o del
    #      resumen), no de una columna.
    Layout(
        name="avantecno",
        signature=re.compile(
            r"Cantidad\s+C[oó]digo\s+Descripci[oó]n\s+Precio\s+Importe\s+Nro\.?\s*Remito", re.I
        ),
        row=re.compile(
            rf"^(?P<qty>\d+)\s+(?P<code>\S+)\s+(?P<desc>.+?)\s+(?P<price>{N})\s+{N}\s+\d+\s*$"
        ),
    ),
    # 10. Service invoices (Prosegur, prepagas, etc.): "CONCEPTO [Cantidad] Importe".
    #     Rows carry only a description and one $ amount (the line TOTAL, so
    #     qty stays 1 and unit_price == amount). No per-line IVA column: the
    #     voucher-letter default applies. Discounts come through as negative
    #     amounts so the line sum still reproduces the printed SUBTOTAL.
    Layout(
        name="concepto_importe",
        signature=re.compile(r"^\s*CONCEPTO\s+(?:Cantidad\s+)?Importe\s*$", re.I),
        row=re.compile(rf"^(?P<desc>.+?)\s+\$\s*(?P<price>-?{N})\s*$"),
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

    for line in lines[hdr + 1 :]:
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


# --------------------------------------------------------------------------
# Totales de control y líneas derivadas de ellos
# --------------------------------------------------------------------------
_TOTAL_PATTERNS = [
    # Portal de ARCA e INCOT: "Importe Total: $ 417855,00" / "Importe Total: $150.660,00".
    re.compile(rf"Importe\s+Total:?\s*\$?\s*({N})", re.I),
    # Dux: "TOTAL Pesos 41,623.19".
    re.compile(rf"TOTAL\s+Pesos\s+({N})", re.I),
    # Polytech factura en pesos y dólares: "Total U$S 201.36 $ 231,561.00" (el que vale es el $).
    re.compile(rf"\bTotal\s+U\$S\s+{N}\s+\$\s*({N})", re.I),
    # Movistar: "Total cargos del período $27.590,00".
    re.compile(rf"Total\s+cargos\s+del\s+per[ií]odo\s*\$?\s*({N})", re.I),
    # Prosegur: "... se facturará, de corresponder, la percepción ... TOTAL $ 41.113,99". Solo
    # espacios entre el $ y el número: con `\s` cruzaría al renglón de abajo cuando el
    # encabezado de una tabla termina en "TOTAL $", y levantaría el primer importe de la fila.
    re.compile(rf"\bTOTAL[ \t]*\$[ \t]*({N})", re.M),
    # Air/NVX: "TOTAL u$s 40,79 $ 43.477,66" (el que vale es el $).
    re.compile(rf"^TOTAL\s+u\$s\s+{N}\s+\$\s*({N})\s*$", re.I | re.M),
    # Segal: el total va al final de la última línea de la leyenda legal: "... detalle de la
    # operación. Total: 203,883.77". Al final, después de los demás, porque "Total:" suelto
    # aparece en otros formatos con otro significado.
    re.compile(rf"\bTotal:\s*\$?\s*({N})\s*$", re.I | re.M),
]


def _extract_total(lines: list[str], text: str) -> Decimal | None:
    for pattern in _TOTAL_PATTERNS:
        m = pattern.search(text)
        if m:
            value = _to_decimal(m.group(1))
            if value is not None:
                # GlobalBluePoint imprime 69,325.0000: cuatro decimales que no son centavos.
                return money(value)
    # Varios ERP (Avantecno, Diamond, Todovisión) imprimen los importes en una fila bajo un
    # encabezado de columnas que termina en "Total": el total es el último número de esa fila.
    for idx, line in enumerate(lines[:-1]):
        if re.search(r"(?:SUBTOTAL|Subt\.?)[^\n]*T\s*o\s*t\s*a\s*l\s*\$?\s*$", line, re.I):
            amounts = re.findall(rf"(?<![\w.,]){N}(?![\w.,])", lines[idx + 1])
            amounts = [a for a in amounts if _MONEY.search(a) or a.isdigit()]
            if amounts:
                value = _to_decimal(amounts[-1])
                if value is not None:
                    return money(value)
    return None


def _extract_tributes_total(text: str) -> Decimal:
    """Suma de percepciones y otros tributos impresos aparte de las líneas.

    Solo lo que el PDF rotula como tributo: "Importe Otros Tributos" (portal de ARCA) y las
    "Per IIBB ..." de los proveedores. El IVA **no** entra: va en las líneas.
    """
    total = Decimal(0)
    for m in re.finditer(rf"Importe\s+Otros\s+Tributos:?\s*\$?\s*({N})", text, re.I):
        total += _to_decimal(m.group(1)) or Decimal(0)
    # Air/NVX: "PERCEPCION: CAPITAL FEDERAL Neto: 38993.42 Alicuota: 1.00% Importe: 389.93 389.93"
    for m in re.finditer(rf"^PERCEPCION\b[^\n]*?Importe:\s*({N})", text, re.I | re.M):
        total += _to_decimal(m.group(1)) or Decimal(0)
    for m in re.finditer(rf"^\s*Per(?:c\w*)?\.?\s*IIBB\b[^\n]*?({N})\s*$", text, re.I | re.M):
        total += _to_decimal(m.group(1)) or Decimal(0)
    # Todovisión: "Perc.IIBB $ 180.99 Perc.IIBB CABA" — el importe va antes del nombre de la
    # jurisdicción, y las otras jurisdicciones (en cero) están en renglones que empiezan con el
    # número, así que no entran por acá.
    for m in re.finditer(rf"^\s*Perc\.?\s*IIBB\s*\$\s*({N})\s+Perc\.?", text, re.I | re.M):
        total += _to_decimal(m.group(1)) or Decimal(0)
    # Neptun (GlobalBluePoint): "Percepción Ingresos Brutos Ciudad de Buenos Aires (1.00%):825,33".
    for m in re.finditer(
        rf"^\s*Percepci[oó]n\s+Ingresos\s+Brutos[^\n]*?\)\s*:\s*({N})", text, re.I | re.M
    ):
        total += _to_decimal(m.group(1)) or Decimal(0)
    # Movistar "Todos": "Ley 27.430 Impuestos Internos 5,2631% 27.798,00 5,26 1.463,04". No es IVA
    # ni percepción, pero está en el total: sin sumarlo la factura no cierra.
    for m in re.finditer(
        rf"^\s*(?:Ley\s+[\d.]+\s+)?Impuestos\s+Internos\b[^\n]*?({N})\s*$", text, re.I | re.M
    ):
        total += _to_decimal(m.group(1)) or Decimal(0)
    # Prosegur: "IB CABA 1,00% $ 337,00" (Ingresos Brutos, con la alícuota antes del importe).
    for m in re.finditer(
        rf"^[ \t]*IB[ \t]+\w+[ \t]+{N}%[ \t]*\$[ \t]*({N})[ \t]*$", text, re.I | re.M
    ):
        total += _to_decimal(m.group(1)) or Decimal(0)
    # Movistar: "Percepción I.V.A. 3,00 662,16" (la alícuota y después el importe).
    for m in re.finditer(
        rf"^[ \t]*Percepci[oó]n[ \t]+I\.?V\.?A\.?(?:[ \t]+{N}){{1,2}}?[ \t]+({N})[ \t]*$",
        text,
        re.I | re.M,
    ):
        total += _to_decimal(m.group(1)) or Decimal(0)
    return total


_IVA_AMOUNT = re.compile(
    rf"I\.?V\.?A\.?[^\n\d]{{0,14}}(27|21|10[.,]5)[\d.,]*\s*[%:][^\n]*?\$?\s*({N})\s*$",
    re.I | re.M,
)
_IVA_CONTENIDO = re.compile(rf"IVA\s+Contenido:?\s*\$?\s*({N})", re.I)


def _lines_with_printed_net(text: str, net_base: Decimal) -> list[ParsedInvoiceLine]:
    """Sin ningún importe de IVA rotulado (Neptun: solo una fila de números bajo el encabezado),
    la alícuota se **prueba** y se acepta solo la que da un neto que el PDF imprime tal cual.
    Adivinarla sin esa prueba cargaría un IVA inventado."""
    for rate in (Decimal("10.5"), Decimal("21"), Decimal("27")):
        net = money(net_base / (1 + rate / 100))
        shown = f"{net:,.2f}"
        variants = {shown, shown.replace(",", "X").replace(".", ",").replace("X", ".")}
        if any(v in text for v in variants):
            return [ParsedInvoiceLine("Según comprobante", Decimal(1), net, rate)]
    return []


def _totals_lines(
    text: str, voucher_type: str | None, total: Decimal | None, tributes: Decimal
) -> list[ParsedInvoiceLine]:
    """Una línea por alícuota (neto e IVA) armada con el resumen impreso del PDF.

    Es el plan B para cuando ningún layout de ítems reconoce la tabla: se pierde el detalle
    de qué se compró, pero **no un peso**, que es lo que importa para cargar el histórico.
    Devuelve `[]` cuando el PDF no trae con qué armarlas; nunca inventa un importe.

    El neto sale siempre **sin IVA**, porque así guarda el unitario esta app (para una B el
    bruto se deriva). En una B el PDF imprime el IVA como "IVA Contenido" y el precio ya
    lo lleva adentro, por eso el neto es total − tributos − IVA.
    """
    if total is None:
        return []
    base = total - tributes
    if voucher_type in ("C", "NCC"):
        return [ParsedInvoiceLine("Según comprobante", Decimal(1), base, Decimal(0))]

    # El PDF del portal y varios ERP imprimen el comprobante dos veces (original y duplicado)
    # en la misma hoja: sin quitar los repetidos el IVA se cuenta doble y el total no cierra.
    found: list[tuple[Decimal, Decimal]] = []
    for rate_text, amount_text in _IVA_AMOUNT.findall(text):
        rate = _to_decimal(rate_text.replace(",", "."))
        amount = _to_decimal(amount_text)
        if rate is not None and amount is not None and amount > 0:
            found.append((rate, amount))
    pairs = list(dict.fromkeys(found))

    if len(pairs) == 1 and base - pairs[0][1] > 0:
        # Una sola alícuota: el neto es lo que sobra, exacto. Deducirlo del IVA pierde
        # centavos (22.003,53 / 10,5% da 209.557,43 y el PDF dice 209.557,47).
        rate, iva = pairs[0]
        return [ParsedInvoiceLine("Según comprobante", Decimal(1), base - iva, rate)]
    if not pairs:
        m = _IVA_CONTENIDO.search(text)
        contained = _to_decimal(m.group(1)) if m else None
        if contained is None:
            return _lines_with_printed_net(text, base)
        net = base - contained
        if net <= 0:
            return []
        if contained == 0:
            # Exempt or zero-rated B: nothing to deduce a rate from, and none is needed.
            return [ParsedInvoiceLine("Según comprobante", Decimal(1), net, Decimal(0))]
        # La alícuota es la que reproduce el IVA impreso: se prueba con las tres que existen
        # en vez de adivinarla, y si ninguna cierra no se devuelve nada.
        for rate in (Decimal("21"), Decimal("10.5"), Decimal("27")):
            if abs(net * rate / 100 - contained) <= Decimal("0.05"):
                return [ParsedInvoiceLine("Según comprobante", Decimal(1), net, rate)]
        return []
    # Varias alícuotas: el neto de cada una se deduce de su IVA. Es aproximado al centavo
    # (la división pierde precisión) pero el total se verifica después contra el impreso.
    return [
        ParsedInvoiceLine("Según comprobante", Decimal(1), money(iva * 100 / rate), rate)
        for rate, iva in pairs
    ]


def lines_gap(parsed: "ParsedInvoice", *, use_totals: bool = False) -> Decimal | None:
    """Diferencia entre lo que suman las líneas leídas y el total que imprime el PDF.

    `None` = no hay total impreso con qué comparar. `0` = cierra. Cualquier otra cosa es un
    layout que leyó mal y **no da error por sí solo**: una columna corrida devuelve líneas
    plausibles con un total distinto que nadie mira hasta la declaración del mes siguiente.

    `lines` trae el precio tal como lo imprime el PDF (en una B, con el IVA adentro);
    `totals_lines` siempre trae neto. Por eso el cálculo cambia según cuál se está mirando.
    """
    if parsed.total is None:
        return None
    items = parsed.totals_lines if use_totals else parsed.lines
    if not items:
        return None
    gross_printed = parsed.voucher_type in ("B", "NCB") and not use_totals
    total = Decimal(0)
    for item in items:
        amount = item.quantity * item.unit_price
        if parsed.voucher_type in ("C", "NCC") or gross_printed:
            total += amount
        else:
            total += amount + amount * item.iva_rate / 100
    total += parsed.tributes_total
    return (total - parsed.total).quantize(Decimal("0.01"))


_REQUIRED_HEADER = ("voucher_type", "pos", "number", "date", "supplier_cuit", "cae")


def is_verified(parsed: "ParsedInvoice") -> bool:
    """Header complete and what was read closes to the cent against the printed total.

    It is the gate for loading anything unattended: a layout that misreads a column (or an
    OCR that drops a digit) returns plausible data that nobody looks at until the monthly
    tax filing. Either the lines or the totals-derived lines must close; if neither does,
    the invoice goes to manual review instead of being loaded.
    """
    if any(getattr(parsed, name) is None for name in _REQUIRED_HEADER):
        return False
    for use_totals in (False, True):
        gap = lines_gap(parsed, use_totals=use_totals)
        if gap is not None and abs(gap) <= Decimal("0.01"):
            return True
    return False


def pdf_text(file_bytes: bytes) -> str:
    """Text layer of the PDF, or "" if it has none (scan) or can't be opened."""
    import io

    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        # Corrupt or scanned PDF that pdfplumber can't read -> manual entry.
        return ""


def parse_invoice_pdf(file_bytes: bytes) -> ParsedInvoice:
    return parse_invoice_text(pdf_text(file_bytes))


def parse_invoice_text(text: str) -> ParsedInvoice:
    """Parse already-extracted text. Shared by the text-layer and the OCR paths, so a
    scan is read by exactly the same layouts (and checked by the same `lines_gap`)."""
    lines = text.split("\n")

    voucher_type = _extract_voucher_type(lines, text)
    pos, number = _extract_pos_number(lines, text)
    date = _extract_date(text)
    supplier_cuit = _extract_supplier_cuit(lines, text)
    supplier_name = _extract_supplier_name(lines, text)
    known = _known_supplier(text, pos)
    if known is not None:
        supplier_cuit, supplier_name = known.cuit, known.name
    supplier_condicion_iva = _extract_condicion_iva(text, voucher_type)

    cae = None
    m = re.search(r"C\.?A\.?E\.?\s*(?:N[°ºo]?\.?)?[:\s#]+(\d{14})", text)
    if m:
        cae = m.group(1)

    items = _extract_items(lines, voucher_type)
    needs_manual_items = not items
    total = _extract_total(lines, text)
    tributes_total = _extract_tributes_total(text)

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
        total=total,
        tributes_total=tributes_total,
        totals_lines=_totals_lines(text, voucher_type, total, tributes_total),
        needs_manual_items=needs_manual_items,
    )
