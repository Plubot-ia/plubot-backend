"""add audit columns to flows table

Revision ID: add_audit_columns_to_flow
Revises: add_node_type_to_flow
Create Date: 2025-05-17 09:03:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'add_audit_columns_to_flow'
down_revision = 'add_node_type_to_flow'
branch_labels = None
depends_on = None


def upgrade():
    # Verificar si las columnas ya existen para evitar errores
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('flows')]
    
    # Añadir columna created_at si no existe
    if 'created_at' not in columns:
        op.add_column('flows', sa.Column('created_at', sa.DateTime, nullable=True, default=datetime.utcnow))
        # Actualizar los valores existentes
        op.execute("UPDATE flows SET created_at = NOW() WHERE created_at IS NULL")
        print("Columna 'created_at' añadida a la tabla 'flows'")
    else:
        print("La columna 'created_at' ya existe en la tabla 'flows'")
    
    # Añadir columna updated_at si no existe
    if 'updated_at' not in columns:
        op.add_column('flows', sa.Column('updated_at', sa.DateTime, nullable=True, default=datetime.utcnow))
        # Actualizar los valores existentes
        op.execute("UPDATE flows SET updated_at = NOW() WHERE updated_at IS NULL")
        print("Columna 'updated_at' añadida a la tabla 'flows'")
    else:
        print("La columna 'updated_at' ya existe en la tabla 'flows'")
    
    # Añadir columna is_deleted si no existe
    if 'is_deleted' not in columns:
        op.add_column('flows', sa.Column('is_deleted', sa.Boolean, nullable=True, default=False))
        # Actualizar los valores existentes
        op.execute("UPDATE flows SET is_deleted = FALSE WHERE is_deleted IS NULL")
        print("Columna 'is_deleted' añadida a la tabla 'flows'")
    else:
        print("La columna 'is_deleted' ya existe en la tabla 'flows'")


def downgrade():
    # Verificar si las columnas existen antes de intentar eliminarlas
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('flows')]
    
    if 'is_deleted' in columns:
        op.drop_column('flows', 'is_deleted')
        print("Columna 'is_deleted' eliminada de la tabla 'flows'")
    else:
        print("La columna 'is_deleted' no existe en la tabla 'flows'")
    
    if 'updated_at' in columns:
        op.drop_column('flows', 'updated_at')
        print("Columna 'updated_at' eliminada de la tabla 'flows'")
    else:
        print("La columna 'updated_at' no existe en la tabla 'flows'")
    
    if 'created_at' in columns:
        op.drop_column('flows', 'created_at')
        print("Columna 'created_at' eliminada de la tabla 'flows'")
    else:
        print("La columna 'created_at' no existe en la tabla 'flows'")
