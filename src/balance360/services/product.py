from sqlalchemy.orm import Session
from balance360.models.product import Product
from balance360.schemas.product import ProductCreate, ProductUpdate
from balance360.crud import product as product_crud
from balance360.exceptions import ProductDeleteError


def delete_product(db: Session, product: Product):
    if product.serial_numbers:
        raise ProductDeleteError(f"No se puede eliminar '{product.name}': tiene seriales asociados")
    product_crud.delete(db, product)

def create_product(db: Session, data: ProductCreate) -> Product:
    return product_crud.create(db, data)

def update_product(db: Session, product: Product, data: ProductUpdate) -> Product:
    return product_crud.update(db, product, data)