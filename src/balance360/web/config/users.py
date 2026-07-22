import json
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from balance360.crud import user as user_crud
from balance360.dependencies import get_current_user, get_db
from balance360.models.user import User
from balance360.schemas.user import UserCreate, UserUpdate
from balance360.web.responses import toast_error
from balance360.web.templating import templates

router = APIRouter(prefix="/users")


def get_user_or_404(user_id: uuid.UUID, db: Session = Depends(get_db)) -> User:
    user = user_crud.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/", response_class=HTMLResponse)
def user_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request, name="users/list.html", context={"users": user_crud.get_all(db)}
    )


@router.get("/close-modal")
def close_modl():
    return HTMLResponse('<div id="modal"></div>')


@router.get("/rows")
def user_rows(
    request: Request, search: str | None = Query(default=""), db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        request=request, name="users/_rows.html", context={"users": user_crud.get_all(db, search)}
    )


@router.get("/new-form")
def new_user_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="users/_form_modal.html",
    )


@router.post("/", response_class=HTMLResponse)
def create_user(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
):
    data = UserCreate(email=email, password=password, full_name=full_name, is_active=True)
    try:
        user_crud.create(db, data)
    except IntegrityError:
        db.rollback()
        return HTMLResponse(
            '<div id="modal"><p class="text-red-600 text-sm p-4">El email ya está registrado.</p></div>'
        )

    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.get("/{user_id}/edit-form")
def user_edit_form(request: Request, user_id: uuid.UUID, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="users/_form_modal.html",
        context={"user": user_crud.get_by_id(db, user_id)},
    )


@router.patch("/{user_id}", response_class=HTMLResponse)
def update_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    email: str | None = Form(default=""),
    full_name: str | None = Form(default=""),
    is_active: bool | None = Form(default=True),
):
    user = user_crud.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = UserUpdate(
        email=email if email else None,
        full_name=full_name if full_name else None,
        is_active=is_active,
    )
    user_crud.update(db, user, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response


@router.delete("/{user_id}")
def delete_user(user_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user = user_crud.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_user = get_current_user(request, db)
    if current_user.id == user.id:
        response = HTMLResponse("")
        response.headers["HX-Trigger"] = (
            '{"showToast": {"message": "No podés eliminar tu propio usuario.", "type": "error"}}'
        )
        response.headers["HX-Reswap"] = "none"
        return response

    user_crud.delete(db, user)
    return HTMLResponse("")


@router.post("/{user_id}/reset-password")
def reset_password(
    request: Request,
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
):
    if len(new_password) < 8:
        return toast_error("Debe tener 8 caracteres como minimo")
    if new_password != new_password_confirm:
        return toast_error("Las passwords no coinciden")

    user_crud.set_password(db, user, new_password)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": "Password actualizada", "type": "success"}}
    )
    return response
