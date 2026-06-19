
class InvoiceAuthorizationError(Exception):
    pass

class InvoicePaymentError(Exception):
    pass

class InvoiceConfirmationError(Exception):
    pass

class InvoiceDeleteError(Exception):
    pass

class RuleConflictError(Exception):
    def __init__(self, pattern: str, count: int) -> None:
        self.pattern = pattern
        self.count = count
