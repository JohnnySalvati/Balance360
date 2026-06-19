import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.product import Product
from balance360.schemas.product import ProductCreate, ProductUpdate

def get_all(db: Session) -> list[Product]:
    products = db.execute(select(Product)).scalars().all()
    return list(products)

def get_by_id(db: Session, product_id: uuid.UUID) -> Product|None:
    product = db.execute(select(Product).where(Product.id == product_id)).scalars().first()
    return product

def create(db: Session, data: ProductCreate) -> Product:
    db_product = Product(**data.model_dump())
    db.add(db_product)
    db.flush()
    db.refresh(db_product)
    return db_product

def  update(db: Session, product: Product, data: ProductUpdate) -> Product:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.flush()
    db.refresh(product)
    return product

def delete(db: Session, product: Product):
    db.delete(product)
    db.flush()


