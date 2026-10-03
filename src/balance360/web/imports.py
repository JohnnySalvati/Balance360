import json
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from balance360.crud import account as account_crud
from balance360.crud import import_batch as import_batch_crud
from balance360.crud import import_row as import_row_crud
from balance360.dependencies import get_db
from balance360.enums import ImportRowStatus
from balance360.exceptions import ImportRowValidationError
from balance360.schemas.import_row import ImportRowUpdate
from balance360.services import import_row as import_row_service
from balance360.services.import_row import ImportRowInput
from balance360.services.import_xlsx import import_workbook
from balance360.web.templating import templates

router = APIRouter(prefix="/imports")


@router.get("/", response_class=HTMLResponse)
def import_page(request: Request, db: Session = Depends(get_db)):

    import_batches = import_batch_crud.get_all(db)

    return templates.TemplateResponse(
        request=request, name="imports/index.html", context={"batches": import_batches}
    )


@router.post("/", response_class=HTMLResponse)
def upload(request: Request, db: Session = Depends(get_db), file: UploadFile = File(...)):
    contents = file.file.read()

    batch = import_workbook(
        db=db, file_bytes=BytesIO(contents), filename=file.filename or "import.xlsx"
    )
    return Response(status_code=200, headers={"HX-Redirect": f"/imports/{batch.id}"})


@router.get("/{batch_id}", response_class=HTMLResponse)
def review_batch(request: Request, batch_id: UUID, db: Session = Depends(get_db)):

    batch = import_batch_crud.get_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")

    rows = import_row_crud.get_by_batch(db, batch_id, ImportRowStatus.needs_review)

    accounts = account_crud.get_all(db)

    return templates.TemplateResponse(
        request=request,
        name="imports/detail.html",
        context={"batch": batch, "rows": rows, "accounts": accounts},
    )


@router.post("/rows/{row_id}/import", response_class=HTMLResponse)
def import_row(
    request: Request,
    row_id: UUID,
    db: Session = Depends(get_db),
    transaction_date: str = Form(""),
    description: str = Form(""),
    amount: str = Form(""),
    type: str = Form(""),
    account_id: str = Form(""),
):
    # Defaults en "" y no `Form(...)`: un campo vacío es un error de la fila que el servicio
    # explica, no un 422 de FastAPI que htmx no muestra.
    import_row_service.import_rows(
        db,
        [
            ImportRowInput(
                row_id=row_id,
                date=transaction_date,
                description=description,
                amount=amount,
                type=type,
                account_id=account_id,
            )
        ],
    )
    return Response(status_code=200)


@router.post("/rows/{row_id}/discard", response_class=HTMLResponse)
def row_discard(request: Request, row_id: UUID, db: Session = Depends(get_db)):
    import_row = import_row_crud.get_by_id(db, row_id)
    if not import_row:
        raise HTTPException(status_code=404, detail="Import row not found")

    import_row_crud.update(db, ImportRowUpdate(status=ImportRowStatus.discarded), import_row)
    return Response(status_code=200)


@router.post("/rows/bulk-import", response_class=HTMLResponse)
def bulk_import(
    request: Request,
    db: Session = Depends(get_db),
    row_ids: list[UUID] = Form([]),
    transaction_date: list[str] = Form([]),
    description: list[str] = Form([]),
    amount: list[str] = Form([]),
    type: list[str] = Form([]),
    account_id: list[str] = Form([]),
):
    # Llegan listas paralelas: el botón incluye los campos de cada fila tildada, y htmx los
    # serializa en orden de documento, así que la posición i de cada lista es la fila i. Si
    # los largos no coinciden algo se perdió en el camino y emparejar por posición mezclaría
    # datos de filas distintas: mejor no importar nada.
    fields = (transaction_date, description, amount, type, account_id)
    if any(len(values) != len(row_ids) for values in fields):
        raise ImportRowValidationError(
            "No se importó nada: el formulario llegó incompleto. Recargá la página."
        )

    inputs = [
        ImportRowInput(row_id=r, date=d, description=desc, amount=a, type=t, account_id=acc)
        for r, d, desc, a, t, acc in zip(row_ids, *fields, strict=True)
    ]
    transactions = import_row_service.import_rows(db, inputs)

    # Todas las filas son del mismo lote: se valida antes de llegar acá que existan.
    row = import_row_crud.get_by_id(db, row_ids[0])
    rows = (
        import_row_crud.get_by_batch(db, row.batch_id, ImportRowStatus.needs_review) if row else []
    )
    accounts = account_crud.get_all(db)
    response = templates.TemplateResponse(
        request=request, name="imports/_rows.html", context={"rows": rows, "accounts": accounts}
    )
    response.headers["HX-Trigger"] = json.dumps(
        {
            "showToast": {
                "message": f"Se importaron {len(transactions)} transacción(es).",
                "type": "success",
            }
        }
    )
    return response


@router.delete("/{batch_id}")
def delete_batch(request: Request, batch_id: UUID, db: Session = Depends(get_db)):
    batch = import_batch_crud.get_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")

    import_batch_crud.delete(db, batch)

    return HTMLResponse("")
