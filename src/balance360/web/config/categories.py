import uuid
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from balance360.dependencies import get_db
from balance360.models.category import Category
from balance360.crud import category as category_crud
from balance360.schemas.category import CategoryCreate, CategoryUpdate
from balance360.web.templating import templates

router = APIRouter(prefix="/categories")

@router.get("/", response_class=HTMLResponse)
def categories_page(request: Request, db: Session = Depends(get_db)):
    categories = category_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="config/categories/list.html",
        context={"categories": categories}
    )

@router.get("/close-modal")
def close_modal():
    return HTMLResponse('<div id="modal"></div>')

@router.get("/rows")
def categories_rows(request: Request, db: Session = Depends(get_db)):
    categories = category_crud.get_all(db)
    return templates.TemplateResponse(
        request=request,
        name="config/categories/_rows.html",
        context={"categories": categories}
    )

@router.get("/new-form")
def new_category_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="config/categories/_form_modal.html",
        context={"categories": category_crud.get_all(db)}
    )

@router.post("/", response_class=HTMLResponse)
def create_category(
        request: Request,
        db: Session = Depends(get_db),
        name: str = Form(...),
        parent_id: str = Form(default=""),
        description: str = Form(default="")
):
    data = CategoryCreate(
        name=name,
        parent_id=uuid.UUID(parent_id) if parent_id else None,
        description=description
    )
    category_crud.create(db, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response

@router.get("/{category_id}/edit-form")
def category_edit_form(request: Request, category_id: uuid.UUID, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="config/categories/_form_modal.html",
        context={
            "category": category_crud.get_by_id(db, category_id),
            "categories": category_crud.get_all(db)
        }
    )

def get_category_or_404(category_id: uuid.UUID, db: Session = Depends(get_db)) -> Category:
    category = category_crud.get_by_id(db, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.patch("/{category_id}", response_class=HTMLResponse)
def update_category(
        category: Category = Depends(get_category_or_404),
        db: Session = Depends(get_db),
        name: str = Form(...),
        parent_id: str = Form(default=""),
        description: str = Form(default="")
):
    data = CategoryUpdate(
        name=name,
        parent_id=uuid.UUID(parent_id) if parent_id else None,
        description=description
    )
    category_crud.update(db, category, data)
    response = HTMLResponse('<div id="modal"></div>')
    response.headers["HX-Trigger"] = "refreshRows"
    return response

@router.delete("/{category_id}", response_class=HTMLResponse)
def delete_category(
    category: Category = Depends(get_category_or_404),
    db: Session = Depends(get_db),
):
    if category.transactions or category.children:
        return HTMLResponse(
            '<tr><td colspan="4" class="px-4 py-2 text-red-600 text-sm">'
            f'No se puede eliminar "{category.name}": tiene subcategorías o transacciones asociadas.'
            '</td></tr>'
        )
    category_crud.delete(db, category)
    return HTMLResponse("")
