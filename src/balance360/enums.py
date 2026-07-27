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
    A = "A"
    B = "B"
    C = "C"
    NCA = "NCA"
    NCB = "NCB"
    NCC = "NCC"
    ND = "ND"


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
    products = "products"
    services = "services"
    both = "both"
