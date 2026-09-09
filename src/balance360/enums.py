import enum
from decimal import Decimal


class AccountType(enum.Enum):
    bank = "bank"
    cash = "cash"
    wallet = "wallet"
    credit_card = "credit_card"


class ContactType(enum.Enum):
    customer = "customer"
    supplier = "supplier"
    both = "both"


class TransactionType(enum.Enum):
    income = "income"
    expense = "expense"


class InvoiceType(enum.Enum):
    purchase = "purchase"
    sale = "sale"


class VoucherType(enum.Enum):
    A = ("A", 1)
    B = ("B", 6)
    C = ("C", 11)
    NCA = ("NCA", 3)
    NCB = ("NCB", 8)
    NCC = ("NCC", 53)

    arca_code: int

    def __new__(cls, letter: str, arca_code: int) -> "VoucherType":
        obj = object.__new__(cls)
        obj._value_ = letter
        obj.arca_code = arca_code
        return obj

    @property
    def is_credit_note(self) -> bool:
        return self in CREDIT_NOTE_VOUCHERS


CREDIT_NOTE_VOUCHERS = (VoucherType.NCA, VoucherType.NCB, VoucherType.NCC)


class SerialStatus(enum.Enum):
    pending = "pending"
    available = "available"
    reserved = "reserved"
    sold = "sold"
    returned = "returned"


class IvaAliquot(enum.Enum):
    exempt = (3, Decimal(0))
    reduced = (4, Decimal(10.5))
    standard = (5, Decimal(21))
    higher = (6, Decimal(27))

    def __init__(self, arca_code: int, rate: Decimal):
        self.arca_code = arca_code
        self.rate = rate


class TributeType(enum.Enum):
    national = 1
    provincial = 2
    municipal = 3
    domestic = 4
    iibb = 5
    iva_perception = 6
    other = 99


class DocType(enum.Enum):
    CUIT = 80
    CUIL = 86
    DNI = 96
    FINAL = 99


class CondicionIva(enum.Enum):
    INSCRIPTO = 1
    EXENTO = 4
    FINAL = 6
    MONOTRIBUTO = 13


class Role(enum.Enum):
    owner = "owner"
    operator = "operator"


class IntervalUnit(enum.Enum):
    """El ritmo de una recurrencia, junto con `interval_count`: cada N dias/semanas/meses/anios.

    Es unidad + cantidad y no un enum de frecuencias cerrado (mensual, quincenal, ...) porque
    con dos columnas entran los sueldos cada dos semanas y los anticipos cada tres meses sin
    agregar miembros. RRULE de RFC 5545 haria lo mismo y mucho mas, pero trae dependencia y
    una gramatica entera para un caso que no la necesita.
    """

    day = "day"
    week = "week"
    month = "month"
    year = "year"


class ClassificationStatus(enum.Enum):
    unclassified = "unclassified"
    auto_classified = "auto_classified"
    manual_no_rule = "manual_no_rule"
    manual_with_rule = "manual_with_rule"


class ImportRowStatus(enum.Enum):
    needs_review = "needs_review"
    imported = "imported"
    discarded = "discarded"


class Concepto(enum.Enum):
    products = ("products", 1)
    services = ("services", 2)
    both = ("both", 3)

    arca_code: int

    def __new__(cls, label: str, arca_code: int) -> "Concepto":
        obj = object.__new__(cls)
        obj._value_ = label
        obj.arca_code = arca_code
        return obj
