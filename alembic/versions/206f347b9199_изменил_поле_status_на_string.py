"""изменил поле status на string

Revision ID: 206f347b9199
Revises: d9978d9f224f
Create Date: 2025-04-04 11:30:58.811139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '206f347b9199'
down_revision: Union[str, None] = 'd9978d9f224f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('order', 'status',
               existing_type=postgresql.ENUM('Подтвержден', 'Неподтвержден', 'Выполнен', name='order_status'),
               type_=sa.String(length=150),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('order', 'status',
               existing_type=sa.String(length=150),
               type_=postgresql.ENUM('Подтвержден', 'Неподтвержден', 'Выполнен', name='order_status'),
               existing_nullable=False)
    # ### end Alembic commands ###
