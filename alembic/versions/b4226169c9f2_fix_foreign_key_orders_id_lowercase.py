"""fix foreign key orders.id lowercase

Revision ID: b4226169c9f2
Revises: f89ec9bc86c1
Create Date: 2025-05-23 14:03:10.530257

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b4226169c9f2'
down_revision: Union[str, None] = 'f89ec9bc86c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Удаляем старый внешний ключ (если был)
    op.drop_constraint('order_item_order_id_fkey', 'order_item', type_='foreignkey')
    # Создаём новый внешний ключ на orders.id
    op.create_foreign_key('order_item_order_id_fkey', 'order_item', 'orders', ['order_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    # Откатываем изменения обратно (если нужно)
    op.drop_constraint('order_item_order_id_fkey', 'order_item', type_='foreignkey')
    op.create_foreign_key('order_item_order_id_fkey', 'order_item', 'Orders', ['order_id'], ['id'], ondelete='CASCADE')