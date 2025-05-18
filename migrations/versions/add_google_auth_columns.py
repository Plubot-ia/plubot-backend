"""add google auth columns

Revision ID: add_google_auth_columns
Revises: e997dd198521
Create Date: 2025-05-18

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_google_auth_columns'
down_revision = 'e997dd198521'  # Ajusta esto según la última migración en tu sistema
branch_labels = None
depends_on = None


def upgrade():
    # Añadir columnas para autenticación con Google
    op.add_column('users', sa.Column('google_id', sa.String(), nullable=True))
    op.add_column('users', sa.Column('google_refresh_token', sa.String(), nullable=True))
    
    # Crear índice único para google_id
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)


def downgrade():
    # Eliminar columnas e índice
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_column('users', 'google_refresh_token')
    op.drop_column('users', 'google_id')
