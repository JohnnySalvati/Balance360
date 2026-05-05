import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from balance360.models.entity import Entity
from balance360.schemas.entity import EntityCreate, EntityUpdate


def get_all(db: Session) -> list[Entity]:
    entities = db.execute(select(Entity)).scalars().all()
    return list(entities)

def get_by_id(db: Session, entity_id: uuid.UUID) -> Entity | None:
    entity = db.execute(select(Entity).where(Entity.id == entity_id)).scalars().first()
    return entity

def create(db: Session, data: EntityCreate) -> Entity:
    db_entity = Entity(**data.model_dump())
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    return db_entity

def delete(db: Session, entity: Entity):
    db.delete(entity)
    db.commit()

def update(db: Session, entity: Entity, data: EntityUpdate):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    db.commit()
    db.refresh(entity)
    return entity
