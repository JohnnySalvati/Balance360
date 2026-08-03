from dataclasses import dataclass
from datetime import date, datetime

from requests.exceptions import RequestException
from zeep.exceptions import Fault

from balance360.database import settings
from balance360.dtos.invoice_request import InvoiceRequest
from balance360.enums import Concepto, VoucherType
from balance360.exceptions import ArcaError, WsfeError
from balance360.services.arca import build_client

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

concepto_code = {Concepto.products: 1, Concepto.services: 2, Concepto.both: 3}


def get_last_voucher_number(
    cuit: str, pos: int, voucher_type: VoucherType, token: str, sign: str
) -> int:

    try:
        client = build_client(WSDL_URL[settings.afip_env])

        response = client.service.FECompUltimoAutorizado(
            Auth={"Token": token, "Sign": sign, "Cuit": cuit},
            PtoVta=pos,
            CbteTipo=voucher_type_code[voucher_type],
        )
    except Fault as e:
        raise WsfeError(f"ARCA: {e}") from e
    except RequestException as e:
        raise ArcaError("No se puede conectar con ARCA, reintenta en unos minutos") from e

    return response.CbteNro or 0


def authorize_invoice(invoice_request: InvoiceRequest) -> AuthorizationResult:

    last_voucher = get_last_voucher_number(
        cuit=invoice_request.auth.cuit,
        pos=invoice_request.voucher_info.pos,
        voucher_type=invoice_request.voucher_info.voucher_type,
        token=invoice_request.auth.token,
        sign=invoice_request.auth.sign,
    )

    imp_neto = (
        sum(line.base_imp for line in invoice_request.voucher_data.iva_detail)
        if invoice_request.voucher_data.iva_detail
        else invoice_request.voucher_data.total
    )
    imp_iva = (
        sum(line.amount for line in invoice_request.voucher_data.iva_detail)
        if invoice_request.voucher_data.iva_detail
        else 0
    )
    imp_trib = sum(line.amount for line in invoice_request.voucher_data.tributes)

    FECAEDetRequest = {
        "Concepto": concepto_code[invoice_request.voucher_data.concepto],
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
        "ImpIVA": imp_iva,
        "ImpTrib": imp_trib,
        "MonId": "PES",
        "MonCotiz": 1,
    }

    if invoice_request.voucher_data.iva_detail:
        FECAEDetRequest["Iva"] = {
            "AlicIva": [
                {
                    "Id": alic_iva_item.id,
                    "BaseImp": alic_iva_item.base_imp,
                    "Importe": alic_iva_item.amount,
                }
                for alic_iva_item in invoice_request.voucher_data.iva_detail
            ]
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

    if invoice_request.voucher_data.associated_vouchers:
        FECAEDetRequest["CbtesAsoc"] = {
            "CbteAsoc": [
                {
                    "Tipo": associated_voucher.tipo,
                    "PtoVta": associated_voucher.pos,
                    "Nro": associated_voucher.number,
                    "Cuit": associated_voucher.cuit,
                    "CbteFch": associated_voucher.date.strftime("%Y%m%d"),
                }
                for associated_voucher in invoice_request.voucher_data.associated_vouchers
            ]
        }

    if invoice_request.voucher_data.concepto is not Concepto.products:
        if (
            invoice_request.voucher_data.from_date
            and invoice_request.voucher_data.to_date
            and invoice_request.voucher_data.due_date
        ):
            FECAEDetRequest["FchServDesde"] = invoice_request.voucher_data.from_date.strftime(
                "%Y%m%d"
            )
            FECAEDetRequest["FchServHasta"] = invoice_request.voucher_data.to_date.strftime(
                "%Y%m%d"
            )
            FECAEDetRequest["FchVtoPago"] = invoice_request.voucher_data.due_date.strftime("%Y%m%d")

    try:
        client = build_client(WSDL_URL[settings.afip_env])

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
    except Fault as e:
        raise WsfeError(f"ARCA: {e}") from e
    except RequestException as e:
        raise ArcaError("No se puede conectar con ARCA, reintenta en unos minutos") from e

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
