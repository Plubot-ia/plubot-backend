"""add frontend_id to flows table

Revision ID: add_frontend_id_to_flow
Revises: add_edge_type_to_flow_edge
Create Date: 2025-05-17 08:48:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_frontend_id_to_flow'
down_revision = 'add_edge_type_to_flow_edge'
branch_labels = None
depends_on = None


def upgrade():
    # Verificar si la columna ya existe para evitar errores
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('flows')]
    
    if 'frontend_id' not in columns:
        op.add_column('flows', sa.Column('frontend_id', sa.String(100), nullable=True))
        op.create_index('idx_flow_frontend_id', 'flows', ['frontend_id'])
        print("Columna 'frontend_id' añadida a la tabla 'flows'")
    else:
        print("La columna 'frontend_id' ya existe en la tabla 'flows'")


def downgrade():
    # Verificar si la columna existe antes de intentar eliminarla
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('flows')]
    
    if 'frontend_id' in columns:
        op.drop_index('idx_flow_frontend_id', table_name='flows')
        op.drop_column('flows', 'frontend_id')
        print("Columna 'frontend_id' eliminada de la tabla 'flows'")
    else:
        print("La columna 'frontend_id' no existe en la tabla 'flows'")
