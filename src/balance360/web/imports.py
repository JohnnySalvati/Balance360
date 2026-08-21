from datetime import date
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from balance360.crud import account as account_crud
from balance360.crud import import_batch as import_batch_crud
from balance360.crud import import_row as import_row_crud
from balance360.crud import transaction as transaction_crud
from balance360.dependencies import get_db
from balance360.enums import ImportRowStatus, TransactionType
from balance360.schemas.import_row import ImportRowUpdate
from balance360.schemas.transaction import TransactionCreate
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
    transaction_date: str = Form(...),
    description: str = Form(...),
    amount: str = Form(...),
    type: str = Form(...),
    account_id: str = Form(...),
):
    row = import_row_crud.get_by_id(db, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="Import row not found")

    data = TransactionCreate(
        date=date.fromisoformat(transaction_date),
        description=description,
        amount=Decimal(amount),
        type=TransactionType(type),
        account_id=UUID(account_id),
        source_file=row.import_batch.filename,
        source_sheet=row.account.name,
        source_row=row.source_row,
        import_batch_id=row.batch_id,
        import_row_id=row.id,
    )
    transaction_crud.create(db, data)

    import_row_crud.update(db, ImportRowUpdate(status=ImportRowStatus.imported), row)

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
    row_ids: list[UUID] = Form(...),
    type: str = Form(...),
    account_id: str = Form(...),
):
    type_parsed = TransactionType(type)
    account_id_parsed = UUID(account_id)
    batch_id = None

    for row_id in row_ids:
        row = import_row_crud.get_by_id(db, row_id)

        if not row:
            continue
        batch_id = row.batch_id
        if not row.date or not row.description:
            continue
        if type_parsed == TransactionType.expense:
            if not row.debit:
                continue
            amount = row.debit
        else:
            if not row.credit:
                continue
            amount = row.credit

        data = TransactionCreate(
            date=row.date,
            description=row.description,
            amount=amount,
            type=type_parsed,
            account_id=account_id_parsed,
            source_file=row.import_batch.filename,
            source_sheet=row.account.name,
            source_row=row.source_row,
            import_batch_id=row.batch_id,
            import_row_id=row.id,
        )
        transaction_crud.create(db, data)

        import_row_crud.update(db, ImportRowUpdate(status=ImportRowStatus.imported), row)

    rows = (
        import_row_crud.get_by_batch(db, batch_id, ImportRowStatus.needs_review) if batch_id else []
    )
    accounts = account_crud.get_all(db)
    return templates.TemplateResponse(
        request=request, name="imports/_rows.html", context={"rows": rows, "accounts": accounts}
    )


@router.delete("/{batch_id}")
def delete_batch(request: Request, batch_id: UUID, db: Session = Depends(get_db)):
    batch = import_batch_crud.get_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")

    import_batch_crud.delete(db, batch)

    return HTMLResponse("")
