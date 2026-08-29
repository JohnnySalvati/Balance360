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


class EmailError(Balance360Error):
    """Fallo al enviar un mail: SMTP sin configurar, rechazo del servidor,
    destinatario ausente. Sube al handler global y sale como toast."""


class IssuedInvoiceError(Balance360Error):
    """No se pudo registrar acá un comprobante que ya emitió otra app (FactuMov).

    Es siempre un problema de datos que le falta a Balance360 —el CUIT que no está cargado, la
    entidad que no se puede deducir, el comprobante que ya estaba— y no una falla de la otra
    app. Por eso el mensaje se propaga tal cual: es lo único que el usuario de FactuMov va a
    ver, y tiene que decirle qué hacer de este lado.
    """


class IssuedInvoiceConflictError(IssuedInvoiceError):
    status = 409


class IssuedInvoiceMismatchError(IssuedInvoiceError):
    """Los importes que reproduce Balance360 no dan los que ARCA autorizó.

    Corta el registro en vez de guardar la diferencia. Un comprobante autorizado cuyo total
    acá no es el del CAE es peor que un comprobante ausente: el ausente se nota, y este se
    arrastra a los reportes y a la declaración sin que nadie lo mire.
    """

    status = 422
