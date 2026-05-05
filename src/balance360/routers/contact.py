
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from balance360.models.contact import Contact
from balance360.schemas.contact import ContactRead, ContactCreate, ContactUpdate
from balance360.crud.contact import get_all, get_by_id, create, delete, update
from balance360.dependencies import get_db

router = APIRouter(prefix="/contacts", tags=["contacts"])

def get_contact_or_404(contact_id: uuid.UUID, db: Session = Depends(get_db)) -> Contact:
    contact = get_by_id(db, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.get("/", response_model=list[ContactRead])
def list_contacts(db: Session = Depends(get_db)):
    return get_all(db)

@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(contact: Contact = Depends(get_contact_or_404)):
    return contact

@router.post("/", response_model=ContactRead)
def create_contact(data: ContactCreate, db: Session =Depends(get_db)):
    return create(db, data)

@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact: Contact = Depends(get_contact_or_404), db: Session = Depends(get_db)):
    delete(db, contact)

@router.patch("/{contact_id}", response_model=Contact)
def update_contact(data: ContactUpdate, contact: Contact = Depends(get_contact_or_404), db: Session = Depends(get_db)):
    update(db, contact, data)