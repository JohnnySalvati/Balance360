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
