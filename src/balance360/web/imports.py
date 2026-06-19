from io import BytesIO
from sqlalchemy.orm import Session
from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, Response
from balance360.crud import import_batch as import_batch_crud
from balance360.services.import_xlsx import import_workbook
from balance360.dependencies import get_db
from balance360.web.templating import templates

router = APIRouter(prefix="/imports")

@router.get("/", response_class=HTMLResponse)
def import_page(
    request: Request,
    db: Session = Depends(get_db)):

    import_batches = import_batch_crud.get_all(db)

    return templates.TemplateResponse(
        request=request,
        name="imports/index.html",
        context={"batches": import_batches}

    )

@router.post("/", response_class=HTMLResponse)
def upload(
    request: Request,
    db: Session = Depends(get_db),
    file: UploadFile = File(...)
):
    contents = file.file.read()

    batch = import_workbook(db=db, file_bytes=BytesIO(contents), filename=file.filename or "import.xlsx")
    
    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/imports/"}
    )
