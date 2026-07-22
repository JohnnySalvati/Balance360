from dataclasses import dataclass
from datetime import date, datetime

from zeep import Client

from balance360.database import settings
from balance360.dtos.invoice_request import InvoiceRequest
from balance360.enums import VoucherType
from balance360.exceptions import WsfeError

WSDL_URL = {
    "homo": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
    "prod": "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL",
}


@dataclass
class AuthorizationResult:
    cae: str
    expiration: date
    number: int


voucher_type_code = {
    VoucherType.A: 1,
    VoucherType.B: 6,
    VoucherType.C: 11,
    VoucherType.NCA: 3,
    VoucherType.NCB: 8,
    VoucherType.NCC: 53,
}


def get_last_voucher_number(
    cuit: str, pos: int, voucher_type: VoucherType, token: str, sign: str
) -> int:
    client = Client(WSDL_URL[settings.afip_env])

    response = client.service.FECompUltimoAutorizado(
        Auth={"Token": token, "Sign": sign, "Cuit": cuit},
        PtoVta=pos,
        CbteTipo=voucher_type_code[voucher_type],
    )

    return response.CbteNro or 0


def authorize_invoice(invoice_request: InvoiceRequest) -> AuthorizationResult:
    client = Client(WSDL_URL[settings.afip_env])

    last_voucher = get_last_voucher_number(
        cuit=invoice_request.auth.cuit,
        pos=invoice_request.voucher_info.pos,
        voucher_type=invoice_request.voucher_info.voucher_type,
        token=invoice_request.auth.token,
        sign=invoice_request.auth.sign,
    )

    imp_neto = sum(line.base_imp for line in invoice_request.voucher_data.iva_detail)
    imp_iva = sum(line.amount for line in invoice_request.voucher_data.iva_detail)
    imp_trib = sum(line.amount for line in invoice_request.voucher_data.tributes)

    FECAEDetRequest = {
        "Concepto": 1,
        "CondicionIVAReceptorId": invoice_request.voucher_data.receiver_condicion_iva.value,
        "DocTipo": invoice_request.voucher_data.receiver_doc_type.value,
        "DocNro": int(invoice_request.voucher_data.receiver_doc_number),
        "CbteDesde": last_voucher + 1,
        "CbteHasta": last_voucher + 1,
        "CbteFch": invoice_request.voucher_data.date.strftime("%Y%m%d"),
        "ImpTotal": invoice_request.voucher_data.total,
        "ImpTotConc": 0,
        "ImpNeto": imp_neto,
        "ImpOpEx": 0,
        "Iva": {
            "AlicIva": [
                {
                    "Id": alic_iva_item.id,
                    "BaseImp": alic_iva_item.base_imp,
                    "Importe": alic_iva_item.amount,
                }
                for alic_iva_item in invoice_request.voucher_data.iva_detail
            ]
        },
        "ImpIVA": imp_iva,
        "ImpTrib": imp_trib,
        "MonId": "PES",
        "MonCotiz": 1,
    }

    if invoice_request.voucher_data.tributes:
        FECAEDetRequest["Tributos"] = {
            "Tributo": [
                {
                    "Id": tribute_item.id,
                    "Desc": tribute_item.description,
                    "BaseImp": tribute_item.base_imp,
                    "Alic": tribute_item.aliquot,
                    "Importe": tribute_item.amount,
                }
                for tribute_item in invoice_request.voucher_data.tributes
            ]
        }

    response = client.service.FECAESolicitar(
        Auth={
            "Token": invoice_request.auth.token,
            "Sign": invoice_request.auth.sign,
            "Cuit": invoice_request.auth.cuit,
        },
        FeCAEReq={
            "FeCabReq": {
                "CantReg": 1,
                "PtoVta": invoice_request.voucher_info.pos,
                "CbteTipo": voucher_type_code[invoice_request.voucher_info.voucher_type],
            },
            "FeDetReq": {"FECAEDetRequest": [FECAEDetRequest]},
        },
    )
    if response.Errors:
        raise WsfeError(
            " --- ".join([f"{error.Code}: {error.Msg}" for error in response.Errors.Err])
        )
    if response.FeDetResp.FECAEDetResponse[0].Resultado != "A":
        raise WsfeError(
            " --- ".join(
                [error.Msg for error in response.FeDetResp.FECAEDetResponse[0].Observaciones.Obs]
            )
        )

    cae = response.FeDetResp.FECAEDetResponse[0].CAE
    expiration = datetime.strptime(
        response.FeDetResp.FECAEDetResponse[0].CAEFchVto, "%Y%m%d"
    ).date()

    return AuthorizationResult(cae=cae, expiration=expiration, number=last_voucher + 1)
