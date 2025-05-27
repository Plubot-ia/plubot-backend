"""Revertir plu_coins a plucoins

Revision ID: 63442b7e59c0
Revises: None
Create Date: 2025-04-22 19:26:33.642349

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '63442b7e59c0'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Verificar si la columna plu_coins existe antes de modificar
    inspector = sa.inspect(op.get_bind())
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'plu_coins' in columns:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('plucoins', sa.Integer(), nullable=True))
            batch_op.drop_column('plu_coins')

def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'plucoins' in columns:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('plu_coins', sa.Integer(), nullable=True))
            batch_op.drop_column('plucoins')