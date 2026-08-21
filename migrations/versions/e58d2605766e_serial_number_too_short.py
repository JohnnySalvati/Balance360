"""serial_number too short

Revision ID: e58d2605766e
Revises: 737a46e7815f
Create Date: 2026-06-25 15:51:34.433550

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "e58d2605766e"
down_revision: Union[str, Sequence[str], None] = "737a46e7815f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Esta revisión se aplicó vacía; el ensanchamiento de serial vive en una
    # migración posterior. No la modifiques: ya está registrada como aplicada.
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
