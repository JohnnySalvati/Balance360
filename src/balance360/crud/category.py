import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.category import Category
from balance360.schemas.category import CategoryCreate, CategoryUpdate

def get_all(db: Session) -> list[Category]:
    categories = db.execute(select(Category)).scalars().all()
    return list(categories)
    
def get_by_id(db: Session, category_id: uuid.UUID) -> Category | None:
    category = db.execute(select(Category).where(Category.id == category_id)).scalars().first()
    return category

def create(db: Session, data: CategoryCreate) -> Category:
    db_category = Category(**data.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def delete(db: Session, category: Category):
    db.delete(category)
    db.commit()

def update(db: Session, category: Category, data: CategoryUpdate) -> Category:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category
    
def get_children(db: Session, category_id: uuid.UUID) -> list[Category]:
    categories = db.execute(select(Category).where(Category.parent_id == category_id)).scalars().all()
    return list(categories)



