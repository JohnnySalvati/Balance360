import enum

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
    NC = "NC"
    ND = "ND"

class SerialStatus(enum.Enum):
    available = "available"
    sold = "sold"
    reserved = "reserved"

class VoucherStatus(enum.Enum):
    draft = "draft"
    pending = "pending"
    paid = "paid"