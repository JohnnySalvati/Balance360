import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from balance360.models.entity import Entity
from balance360.models.entity_membership import EntityMembership
from balance360.schemas.entity import EntityCreate, EntityUpdate
from balance360.crud import entity_membership as entity_membership_crud

def get_all(db: Session, search: str|None=None) -> list[Entity]:
    stmt = select(Entity)

    if search:
        stmt = stmt.where(Entity.name.ilike(f"%{search.strip()}%"))
    
    stmt = stmt.order_by(Entity.name)
    entities = db.execute(stmt).scalars().all()
    
    return list(entities)

def get_by_user(db: Session, user_id: uuid.UUID) -> list[Entity]:
    stmt = select(Entity).join(EntityMembership, EntityMembership.entity_id == Entity.id).where(EntityMembership.user_id == user_id)
    entities = db.execute(stmt).scalars().all()

    return list(entities)

def get_by_id(db: Session, entity_id: uuid.UUID) -> Entity | None:
    entity = db.execute(select(Entity).where(Entity.id == entity_id)).scalars().first()
    return entity

def create(db: Session, data: EntityCreate) -> Entity:
    db_entity = Entity(**data.model_dump())
    db.add(db_entity)
    db.flush()
    db.refresh(db_entity)
    return db_entity

def delete(db: Session, entity: Entity):
    db.delete(entity)
    db.flush()

def update(db: Session, entity: Entity, data: EntityUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    db.flush()
    db.refresh(entity)
    return entity
