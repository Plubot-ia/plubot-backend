"""add node_type to flows table

Revision ID: add_node_type_to_flow
Revises: add_frontend_id_to_flow
Create Date: 2025-05-17 08:59:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_node_type_to_flow'
down_revision = 'add_frontend_id_to_flow'
branch_labels = None
depends_on = None


def upgrade():
    # Verificar si la columna ya existe para evitar errores
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('flows')]
    
    if 'node_type' not in columns:
        op.add_column('flows', sa.Column('node_type', sa.String(50), nullable=True))
        print("Columna 'node_type' añadida a la tabla 'flows'")
    else:
        print("La columna 'node_type' ya existe en la tabla 'flows'")


def downgrade():
    # Verificar si la columna existe antes de intentar eliminarla
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('flows')]
    
    if 'node_type' in columns:
        op.drop_column('flows', 'node_type')
        print("Columna 'node_type' eliminada de la tabla 'flows'")
    else:
        print("La columna 'node_type' no existe en la tabla 'flows'")
