import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from balance360.models.entity_membership import EntityMembership
from balance360.schemas.entity_membership import EntityMembershipCreate, EntityMembershipUpdate

def get_by_id(db: Session, entity_membership_id: uuid.UUID) -> EntityMembership|None:
    return db.execute(select(EntityMembership).where(EntityMembership.id == entity_membership_id)).scalars().first()

def get_by_entity(db: Session, entity_id: uuid.UUID) -> list[EntityMembership]:
    entity_memberships =  db.execute(select(EntityMembership).where(EntityMembership.entity_id == entity_id)).scalars().all()
    return list(entity_memberships)

def create(db: Session, data: EntityMembershipCreate) -> EntityMembership:
    entity_membership = EntityMembership(**data.model_dump())
    db.add(entity_membership)
    db.flush()
    db.refresh(entity_membership)
    return entity_membership

def update(db: Session, data: EntityMembershipUpdate, entity_membership: EntityMembership) -> EntityMembership:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entity_membership, field, value)
    db.flush()
    db.refresh(entity_membership)
    return entity_membership

def delete(db: Session, entity_membership: EntityMembership):
    db.delete(entity_membership)
    db.flush()

