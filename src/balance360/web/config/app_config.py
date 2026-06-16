from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from balance360.dependencies import get_db
from balance360.crud import app_config as app_config_crud
from balance360.schemas.app_config import AppconfigUpdate
router = APIRouter(prefix="/app-config")
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")

@router.get("/", response_class=HTMLResponse)
def app_config_page(
    request: Request,
    db: Session = Depends(get_db)
):
    app_config = app_config_crud.get(db)

    return templates.TemplateResponse(
        request=request,
        name="config/app_config/list.html",
        context={"app_config": app_config}
    )

@router.patch("/", response_class=HTMLResponse)
def update_app_config(
    request: Request,
    db: Session = Depends(get_db),
):
    data = AppconfigUpdate(

    )
    app_config_crud.save(db, data)
    response = HTMLResponse("")
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Configuración guardada.", "type": "success"}}'
    return response

