import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from balance360.models.entity import Entity
from balance360.schemas.entity import EntityRead, EntityCreate, EntityUpdate
from balance360.crud.entity import get_all, get_by_id, create, delete, update
from balance360.dependencies import get_db

router = APIRouter(prefix="/entities", tags=["entities"])

def get_entity_or_404(entity_id: uuid.UUID, db: Session = Depends(get_db)) -> Entity:
    entity = get_by_id(db, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity

@router.get("/", response_model=list[EntityRead])
def list_entities(db: Session = Depends(get_db)):
    return get_all(db)

@router.get("/{entity_id}", response_model=EntityRead)
def get_entity(entity: Entity = Depends(get_entity_or_404)):
    return entity

@router.post("/", response_model=EntityRead)
def create_entity(data: EntityCreate, db: Session = Depends(get_db)):
    return create(db, data)

@router.delete("/{entity_id}", status_code=204)
def delete_entity(entity: Entity = Depends(get_entity_or_404), db: Session = Depends(get_db)):
    delete(db, entity)

@router.patch("/{entity_id}", response_model=EntityRead)
def update_entity(data: EntityUpdate, entity: Entity = Depends(get_entity_or_404), db: Session = Depends(get_db)):
    return update(db, entity, data)
