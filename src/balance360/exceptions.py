class Balance360Error(Exception):
    status = 400


class InvoiceAuthorizationError(Balance360Error):
    pass


class InvoicePaymentError(Balance360Error):
    pass


class InvoiceConfirmationError(Balance360Error):
    pass


class InvoiceDeleteError(Balance360Error):
    pass


class InvoiceRequestError(Balance360Error):
    pass


class InvoiceCreditNoteError(Balance360Error):
    pass


class InvoicePrintError(Balance360Error):
    status = 409


class RuleConflictError(Balance360Error):
    def __init__(self, pattern: str, count: int) -> None:
        super().__init__(self)
        self.pattern = pattern
        self.count = count


class ProductDeleteError(Balance360Error):
    pass


class SerialValidationError(Balance360Error):
    pass


class SyncServiceError(Balance360Error):
    pass


class CurrencyDeleteError(Balance360Error):
    pass


class ImportServiceError(Balance360Error):
    pass


class ArcaError(Balance360Error):
    pass


class PadronError(Balance360Error):
    """Consulta al padron que ARCA respondio, pero sin datos utiles.

    No hereda de ArcaError a proposito: un CUIT inexistente es un error del dato
    que cargo el usuario, no una falla del servicio, y el handler de main.py
    loguea ArcaError con traceback.
    """


class WsfeError(ArcaError):
    pass


class WsaaError(ArcaError):
    pass


class QrValidationError(Balance360Error):
    pass
