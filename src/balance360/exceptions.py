class InvoiceAuthorizationError(Exception):
    pass


class InvoicePaymentError(Exception):
    pass


class InvoiceConfirmationError(Exception):
    pass


class InvoiceDeleteError(Exception):
    pass


class InvoiceRequestError(Exception):
    pass


class RuleConflictError(Exception):
    def __init__(self, pattern: str, count: int) -> None:
        self.pattern = pattern
        self.count = count


class ProductDeleteError(Exception):
    pass


class SerialValidationError(Exception):
    pass


class SyncServiceError(Exception):
    pass


class CurrencyDeleteError(Exception):
    pass


class ImportServiceError(Exception):
    pass


class ArcaError(Exception):
    pass


class WsfeError(ArcaError):
    pass


class WsaaError(ArcaError):
    pass
