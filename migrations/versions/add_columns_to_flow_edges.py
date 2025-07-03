"""add columns to flow_edges table

Revision ID: add_columns_to_flow_edges
Revises: add_audit_columns_to_flow
Create Date: 2025-05-17 09:04:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'add_columns_to_flow_edges'
down_revision = 'add_audit_columns_to_flow'
branch_labels = None
depends_on = None


def upgrade():
    # Verificar si las columnas ya existen para evitar errores
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('flow_edges')]
    
    # Añadir columna label si no existe
    if 'label' not in columns:
        op.add_column('flow_edges', sa.Column('label', sa.String(255), nullable=True))
        print("Columna 'label' añadida a la tabla 'flow_edges'")
    else:
        print("La columna 'label' ya existe en la tabla 'flow_edges'")
    
    # Añadir columna created_at si no existe
    if 'created_at' not in columns:
        op.add_column('flow_edges', sa.Column('created_at', sa.DateTime, nullable=True, default=datetime.utcnow))
        # Actualizar los valores existentes
        op.execute("UPDATE flow_edges SET created_at = NOW() WHERE created_at IS NULL")
        print("Columna 'created_at' añadida a la tabla 'flow_edges'")
    else:
        print("La columna 'created_at' ya existe en la tabla 'flow_edges'")
    
    # Añadir columna updated_at si no existe
    if 'updated_at' not in columns:
        op.add_column('flow_edges', sa.Column('updated_at', sa.DateTime, nullable=True, default=datetime.utcnow))
        # Actualizar los valores existentes
        op.execute("UPDATE flow_edges SET updated_at = NOW() WHERE updated_at IS NULL")
        print("Columna 'updated_at' añadida a la tabla 'flow_edges'")
    else:
        print("La columna 'updated_at' ya existe en la tabla 'flow_edges'")
    
    # Añadir columna is_deleted si no existe
    if 'is_deleted' not in columns:
        op.add_column('flow_edges', sa.Column('is_deleted', sa.Boolean, nullable=True, default=False))
        # Actualizar los valores existentes
        op.execute("UPDATE flow_edges SET is_deleted = FALSE WHERE is_deleted IS NULL")
        print("Columna 'is_deleted' añadida a la tabla 'flow_edges'")
    else:
        print("La columna 'is_deleted' ya existe en la tabla 'flow_edges'")


def downgrade():
    # Verificar si las columnas existen antes de intentar eliminarlas
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('flow_edges')]
    
    if 'is_deleted' in columns:
        op.drop_column('flow_edges', 'is_deleted')
        print("Columna 'is_deleted' eliminada de la tabla 'flow_edges'")
    else:
        print("La columna 'is_deleted' no existe en la tabla 'flow_edges'")
    
    if 'updated_at' in columns:
        op.drop_column('flow_edges', 'updated_at')
        print("Columna 'updated_at' eliminada de la tabla 'flow_edges'")
    else:
        print("La columna 'updated_at' no existe en la tabla 'flow_edges'")
    
    if 'created_at' in columns:
        op.drop_column('flow_edges', 'created_at')
        print("Columna 'created_at' eliminada de la tabla 'flow_edges'")
    else:
        print("La columna 'created_at' no existe en la tabla 'flow_edges'")
    
    if 'label' in columns:
        op.drop_column('flow_edges', 'label')
        print("Columna 'label' eliminada de la tabla 'flow_edges'")
    else:
        print("La columna 'label' no existe en la tabla 'flow_edges'")
