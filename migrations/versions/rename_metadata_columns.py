"""
Renombrar columnas metadata a node_metadata y edge_metadata

Revision ID: 8f4b1a9c7d3e
Revises: add_edge_type_to_flow_edge
Create Date: 2025-05-17 08:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8f4b1a9c7d3e'
down_revision = '08175f882318'  # Usar la revisión head actual
branch_labels = None
depends_on = None


def upgrade():
    # Verificar si la columna metadata existe en la tabla flows
    from sqlalchemy.engine.reflection import Inspector
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Agregar columna node_metadata a la tabla flows si no existe
    if 'metadata' in [c['name'] for c in inspector.get_columns('flows')]:
        # Si existe, renombrarla
        op.alter_column('flows', 'metadata', new_column_name='node_metadata')
    elif 'node_metadata' not in [c['name'] for c in inspector.get_columns('flows')]:
        # Si no existe ni metadata ni node_metadata, agregar node_metadata
        op.add_column('flows', sa.Column('node_metadata', sa.JSON(), nullable=True))
    
    # Agregar columna edge_metadata a la tabla flow_edges si no existe
    if 'metadata' in [c['name'] for c in inspector.get_columns('flow_edges')]:
        # Si existe, renombrarla
        op.alter_column('flow_edges', 'metadata', new_column_name='edge_metadata')
    elif 'edge_metadata' not in [c['name'] for c in inspector.get_columns('flow_edges')]:
        # Si no existe ni metadata ni edge_metadata, agregar edge_metadata
        op.add_column('flow_edges', sa.Column('edge_metadata', sa.JSON(), nullable=True))


def downgrade():
    # Verificar si las columnas existen antes de intentar renombrarlas
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Revertir cambios en la tabla flows
    if 'node_metadata' in [c['name'] for c in inspector.get_columns('flows')]:
        if 'metadata' not in [c['name'] for c in inspector.get_columns('flows')]:
            # Si node_metadata existe pero metadata no, renombrar node_metadata a metadata
            op.alter_column('flows', 'node_metadata', new_column_name='metadata')
        else:
            # Si ambas existen, eliminar node_metadata
            op.drop_column('flows', 'node_metadata')
    
    # Revertir cambios en la tabla flow_edges
    if 'edge_metadata' in [c['name'] for c in inspector.get_columns('flow_edges')]:
        if 'metadata' not in [c['name'] for c in inspector.get_columns('flow_edges')]:
            # Si edge_metadata existe pero metadata no, renombrar edge_metadata a metadata
            op.alter_column('flow_edges', 'edge_metadata', new_column_name='metadata')
        else:
            # Si ambas existen, eliminar edge_metadata
            op.drop_column('flow_edges', 'edge_metadata')
