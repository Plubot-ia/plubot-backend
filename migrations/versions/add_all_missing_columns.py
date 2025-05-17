"""add all missing columns to flows and flow_edges tables

Revision ID: add_all_missing_columns
Revises: add_columns_to_flow_edges
Create Date: 2025-05-17 09:06:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'add_all_missing_columns'
down_revision = 'add_columns_to_flow_edges'
branch_labels = None
depends_on = None


def upgrade():
    # Verificar columnas existentes en flows
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    flows_columns = [col['name'] for col in inspector.get_columns('flows')]
    flow_edges_columns = [col['name'] for col in inspector.get_columns('flow_edges')]
    
    # ====== TABLA FLOWS ======
    # Columnas de contenido
    if 'node_type' not in flows_columns:
        op.add_column('flows', sa.Column('node_type', sa.String(50), default="message"))
        print("Columna 'node_type' añadida a la tabla 'flows'")
    
    if 'node_metadata' not in flows_columns:
        op.add_column('flows', sa.Column('node_metadata', sa.JSON, nullable=True))
        print("Columna 'node_metadata' añadida a la tabla 'flows'")
    
    if 'frontend_id' not in flows_columns:
        op.add_column('flows', sa.Column('frontend_id', sa.String(100), nullable=True))
        op.create_index('idx_flow_frontend_id', 'flows', ['frontend_id'])
        print("Columna 'frontend_id' añadida a la tabla 'flows'")
    
    # Columnas de auditoría para flows
    if 'created_at' not in flows_columns:
        op.add_column('flows', sa.Column('created_at', sa.DateTime, nullable=True, default=datetime.utcnow))
        op.execute("UPDATE flows SET created_at = NOW() WHERE created_at IS NULL")
        print("Columna 'created_at' añadida a la tabla 'flows'")
    
    if 'updated_at' not in flows_columns:
        op.add_column('flows', sa.Column('updated_at', sa.DateTime, nullable=True, default=datetime.utcnow))
        op.execute("UPDATE flows SET updated_at = NOW() WHERE updated_at IS NULL")
        print("Columna 'updated_at' añadida a la tabla 'flows'")
    
    if 'is_deleted' not in flows_columns:
        op.add_column('flows', sa.Column('is_deleted', sa.Boolean, nullable=True, default=False))
        op.execute("UPDATE flows SET is_deleted = FALSE WHERE is_deleted IS NULL")
        print("Columna 'is_deleted' añadida a la tabla 'flows'")
    
    # ====== TABLA FLOW_EDGES ======
    # Campos funcionales
    if 'condition' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('condition', sa.Text, default=""))
        print("Columna 'condition' añadida a la tabla 'flow_edges'")
    
    if 'label' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('label', sa.String(255), nullable=True))
        print("Columna 'label' añadida a la tabla 'flow_edges'")
    
    # Campos técnicos para UI
    if 'edge_type' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('edge_type', sa.String(50), default="default"))
        print("Columna 'edge_type' añadida a la tabla 'flow_edges'")
    
    if 'frontend_id' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('frontend_id', sa.String(100), nullable=True))
        op.create_index('idx_flow_edge_frontend_id', 'flow_edges', ['frontend_id'])
        print("Columna 'frontend_id' añadida a la tabla 'flow_edges'")
    
    if 'source_handle' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('source_handle', sa.String(50), nullable=True))
        print("Columna 'source_handle' añadida a la tabla 'flow_edges'")
    
    if 'target_handle' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('target_handle', sa.String(50), nullable=True))
        print("Columna 'target_handle' añadida a la tabla 'flow_edges'")
    
    # Estilos y metadatos
    if 'style' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('style', sa.JSON, nullable=True))
        print("Columna 'style' añadida a la tabla 'flow_edges'")
    
    if 'edge_metadata' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('edge_metadata', sa.JSON, nullable=True))
        print("Columna 'edge_metadata' añadida a la tabla 'flow_edges'")
    
    # Columnas de auditoría para flow_edges
    if 'created_at' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('created_at', sa.DateTime, nullable=True, default=datetime.utcnow))
        op.execute("UPDATE flow_edges SET created_at = NOW() WHERE created_at IS NULL")
        print("Columna 'created_at' añadida a la tabla 'flow_edges'")
    
    if 'updated_at' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('updated_at', sa.DateTime, nullable=True, default=datetime.utcnow))
        op.execute("UPDATE flow_edges SET updated_at = NOW() WHERE updated_at IS NULL")
        print("Columna 'updated_at' añadida a la tabla 'flow_edges'")
    
    if 'is_deleted' not in flow_edges_columns:
        op.add_column('flow_edges', sa.Column('is_deleted', sa.Boolean, nullable=True, default=False))
        op.execute("UPDATE flow_edges SET is_deleted = FALSE WHERE is_deleted IS NULL")
        print("Columna 'is_deleted' añadida a la tabla 'flow_edges'")


def downgrade():
    # Eliminar columnas de flow_edges
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    flow_edges_columns = [col['name'] for col in inspector.get_columns('flow_edges')]
    
    if 'is_deleted' in flow_edges_columns:
        op.drop_column('flow_edges', 'is_deleted')
    if 'updated_at' in flow_edges_columns:
        op.drop_column('flow_edges', 'updated_at')
    if 'created_at' in flow_edges_columns:
        op.drop_column('flow_edges', 'created_at')
    if 'edge_metadata' in flow_edges_columns:
        op.drop_column('flow_edges', 'edge_metadata')
    if 'style' in flow_edges_columns:
        op.drop_column('flow_edges', 'style')
    if 'target_handle' in flow_edges_columns:
        op.drop_column('flow_edges', 'target_handle')
    if 'source_handle' in flow_edges_columns:
        op.drop_column('flow_edges', 'source_handle')
    if 'frontend_id' in flow_edges_columns:
        op.drop_index('idx_flow_edge_frontend_id', 'flow_edges')
        op.drop_column('flow_edges', 'frontend_id')
    if 'edge_type' in flow_edges_columns:
        op.drop_column('flow_edges', 'edge_type')
    if 'label' in flow_edges_columns:
        op.drop_column('flow_edges', 'label')
    if 'condition' in flow_edges_columns:
        op.drop_column('flow_edges', 'condition')
    
    # Eliminar columnas de flows
    flows_columns = [col['name'] for col in inspector.get_columns('flows')]
    
    if 'is_deleted' in flows_columns:
        op.drop_column('flows', 'is_deleted')
    if 'updated_at' in flows_columns:
        op.drop_column('flows', 'updated_at')
    if 'created_at' in flows_columns:
        op.drop_column('flows', 'created_at')
    if 'frontend_id' in flows_columns:
        op.drop_index('idx_flow_frontend_id', 'flows')
        op.drop_column('flows', 'frontend_id')
    if 'node_metadata' in flows_columns:
        op.drop_column('flows', 'node_metadata')
    if 'node_type' in flows_columns:
        op.drop_column('flows', 'node_type')
