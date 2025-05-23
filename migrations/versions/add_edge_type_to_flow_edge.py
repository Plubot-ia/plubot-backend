"""add edge_type to flow_edge

Revision ID: add_edge_type_to_flow_edge
Revises: 
Create Date: 2025-05-14 16:32:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_edge_type_to_flow_edge'
down_revision = None  # Ajustar según la última migración
branch_labels = None
depends_on = None


def upgrade():
    # Verificar si la columna edge_type ya existe en la tabla flow_edges
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Obtener las columnas existentes en la tabla flow_edges
    columns = [c['name'] for c in inspector.get_columns('flow_edges')]
    
    # Solo agregar la columna si no existe
    if 'edge_type' not in columns:
        # Añadir la columna edge_type a la tabla flow_edges
        op.add_column('flow_edges', sa.Column('edge_type', sa.String(50), nullable=True))
        
        # Actualizar los registros existentes para establecer un valor por defecto
        op.execute("UPDATE flow_edges SET edge_type = 'default' WHERE edge_type IS NULL")
        
        # Hacer la columna no nullable después de actualizar los valores existentes
        op.alter_column('flow_edges', 'edge_type', nullable=False, server_default='default')


def downgrade():
    # Verificar si la columna edge_type existe en la tabla flow_edges
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Obtener las columnas existentes en la tabla flow_edges
    columns = [c['name'] for c in inspector.get_columns('flow_edges')]
    
    # Solo eliminar la columna si existe
    if 'edge_type' in columns:
        # Eliminar la columna edge_type de la tabla flow_edges
        op.drop_column('flow_edges', 'edge_type')
