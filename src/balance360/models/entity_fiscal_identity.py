# association table — two FKs, composite PK, nothing else
from sqlalchemy import Table, Column, ForeignKey

from balance360.models.base import Base

entity_fiscal_identities = Table(
    "entity_fiscal_identities",
    Base.metadata,
    Column("entity_id", ForeignKey("entities.id"), primary_key=True),
    Column("fiscal_identity_id", ForeignKey("fiscal_identities.id"), primary_key=True),
)
