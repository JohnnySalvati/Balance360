"""Que una entidad se pueda serializar para salir por `/api`.

Parece un test de nada —validar un schema contra un modelo— y sin embargo es el que faltaba
para que `GET /api/entities` no fuera un 500. `EntityRead` pide `fiscal_identity_ids` y la
relación del modelo se llama `fiscal_identities`: con `from_attributes`, pydantic busca el
atributo por nombre, no lo encuentra, y lo que no valida es **la respuesta**, que es un error
del servidor y no del que llama.

Nadie se había enterado porque la web no pasa por acá: arma su HTML desde las entidades del
CRUD. El primer cliente real de estos endpoints fue FactuMov, que prueba el token contra
`/api/entities` justo porque es el más barato de todos.
"""

from balance360.schemas.entity import EntityRead
from tests.factories import make_entity, make_fiscal_identity


def test_una_entidad_se_serializa_con_los_ids_de_sus_identidades(db):
    entity = make_entity(db, name="InSoft")
    identity = make_fiscal_identity(db, name="InSoft SRL")
    entity.fiscal_identities.append(identity)
    db.commit()

    read = EntityRead.model_validate(entity)

    assert read.name == "InSoft"
    assert read.fiscal_identity_ids == [identity.id]


def test_una_entidad_sin_identidades_tambien_se_serializa(db):
    """El caso más común de todos, y el que un `[]` por defecto haría pasar por casualidad."""
    entity = make_entity(db, name="Casa")

    read = EntityRead.model_validate(entity)

    assert read.fiscal_identity_ids == []
