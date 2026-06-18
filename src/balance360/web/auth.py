from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.crud import user as user_crud
from balance360.services.auth import create_access_token
from balance360.web.templating import templates

router = APIRouter(prefix="/login")

@router.get("/", response_class=HTMLResponse)
def login_form(
    request: Request,
):
    return templates.TemplateResponse(
        request=request,
        name="auth/_form.html",
    )

@router.post("/", response_class=RedirectResponse)
def login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...)
    ):

    user = user_crud.get_by_email(db, email)

    if not user or not user_crud.verify_user_password(user, password):
        return templates.TemplateResponse(
            request=request,
            name="auth/_form.html",
            context={"error": "Email o contraseña incorrectos"}
        )
    
    token = create_access_token(user.id)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("access_token", token, httponly=True)
    
    return response

