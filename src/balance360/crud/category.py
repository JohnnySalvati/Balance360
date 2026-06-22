import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.category import Category
from balance360.schemas.category import CategoryCreate, CategoryUpdate

def get_all(db: Session, search: str|None=None) -> list[Category]:

    search = search.lower() if search else None
    
    def flatten(node: Category, all_categories: list[Category], search: str|None = None):
        result = [node]
        children = [c for c in all_categories if c.parent_id == node.id]
        
        for child in children:
            result.extend(flatten(child, all_categories, search))
        
        if search and len(result) == 1 and search not in node.name.lower():
            return []
        
        return result
    
    stmt = select(Category).order_by(Category.name)
    categories = list(db.execute(stmt).scalars().all())

    root_categories = [cat for cat in categories if not cat.parent_id]
    
    result = []

    for root_category in root_categories:
        children = flatten(root_category, categories, search)

        result.extend(children)
    
    return result
    
def get_by_id(db: Session, category_id: uuid.UUID) -> Category | None:
    category = db.execute(select(Category).where(Category.id == category_id)).scalars().first()
    return category

def create(db: Session, data: CategoryCreate) -> Category:
    db_category = Category(**data.model_dump())
    db.add(db_category)
    db.flush()
    db.refresh(db_category)
    return db_category

def delete(db: Session, category: Category):
    db.delete(category)
    db.flush()


def update(db: Session, category: Category, data: CategoryUpdate) -> Category:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.flush()
    db.refresh(category)
    return category
    
def get_children(db: Session, category_id: uuid.UUID) -> list[Category]:
    categories = db.execute(select(Category)
                            .where(Category.parent_id == category_id)
                            .order_by(Category.name)
                            ).scalars().all()
    return list(categories)



