"""Rename user table to users

Revision ID: 5b34c3518bdc
Revises: a3565bbc18a8
Create Date: 2025-04-02 00:05:24.765158
"""

from alembic import op

# Revision identifiers, used by Alembic.
revision = '5b34c3518bdc'
down_revision = 'a3565bbc18a8'
branch_labels = None
depends_on = None


def upgrade():
    """Переименование таблицы user в users и обновление внешних ключей."""
    op.drop_constraint('cart_user_id_fkey', 'cart', type_='foreignkey')
    op.drop_constraint('order_user_id_fkey', 'order', type_='foreignkey')

    op.execute('ALTER TABLE "user" RENAME TO users')

    op.create_foreign_key('cart_user_id_fkey', 'cart', 'users', ['user_id'], ['user_id'], ondelete='CASCADE')
    op.create_foreign_key('order_user_id_fkey', 'order', 'users', ['user_id'], ['user_id'], ondelete='CASCADE')


def downgrade():
    """Откат: переименование обратно и восстановление внешних ключей."""
    op.drop_constraint('cart_user_id_fkey', 'cart', type_='foreignkey')
    op.drop_constraint('order_user_id_fkey', 'order', type_='foreignkey')

    op.execute('ALTER TABLE users RENAME TO "user"')

    op.create_foreign_key('cart_user_id_fkey', 'cart', 'user', ['user_id'], ['user_id'], ondelete='CASCADE')
    op.create_foreign_key('order_user_id_fkey', 'order', 'user', ['user_id'], ['user_id'], ondelete='CASCADE')
