import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from balance360.models.category import Category
from balance360.schemas.category import CategoryRead, CategoryCreate, CategoryUpdate
from balance360.crud.category import get_all, get_by_id, create, delete, update, get_children
from balance360.dependencies import get_db

router = APIRouter(prefix="/categories", tags=["categories"])

def get_category_or_404(category_id: uuid.UUID, db: Session = Depends(get_db)) -> Category:
    category = get_by_id(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.get("/", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)):
    return get_all(db)

@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category: Category = Depends(get_category_or_404)):
    return category

@router.post("/", response_model=CategoryRead)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    return create(db, data)

@router.delete("/{category_id}", status_code=204)
def delete_category(category: Category = Depends(get_category_or_404), db: Session = Depends(get_db)):
    delete(db, category)

@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(data: CategoryUpdate, category: Category = Depends(get_category_or_404), db: Session = Depends(get_db)):
    return update(db, category, data)
    
@router.get("/{category_id}/children", response_model=list[CategoryRead])
def get_category_children(category_id: uuid.UUID, db: Session= Depends(get_db)):
    return get_children(db, category_id)

