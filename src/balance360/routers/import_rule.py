from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from balance360.crud.import_rule import get_all
from balance360.dependencies import get_db
from balance360.schemas.import_rule import ImportRuleRead

router = APIRouter(prefix="/import_rules", tags=["import_rules"])


@router.get("/", response_model=list[ImportRuleRead])
def list_import_rules(db: Session = Depends(get_db)):
    return get_all(db)
