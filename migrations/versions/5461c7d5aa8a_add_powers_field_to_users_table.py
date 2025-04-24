"""Add powers field to users table

Revision ID: 5461c7d5aa8a
Revises: e997dd198521
Create Date: 2025-04-24 02:00:43.120
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# Variables requeridas por Alembic
revision = '5461c7d5aa8a'
down_revision = 'e997dd198521'
branch_labels = None
depends_on = None

def upgrade():
    # Añadir la columna powers como JSONB sin la restricción NOT NULL inicialmente
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('powers', JSONB(), nullable=True))

    # Establecer un valor por defecto de [] para los registros existentes
    op.execute("UPDATE users SET powers = '[]'::jsonb WHERE powers IS NULL")

    # Añadir la restricción NOT NULL después de asegurar que no hay valores nulos
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('powers', nullable=False)

def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('powers')