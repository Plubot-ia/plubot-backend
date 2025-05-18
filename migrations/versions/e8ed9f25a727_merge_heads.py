"""merge_heads

Revision ID: e8ed9f25a727
Revises: add_edge_type_to_flow_edge, 8f4b1a9c7d3e
Create Date: 2025-05-17 08:18:48.027335

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8ed9f25a727'
down_revision = ('add_edge_type_to_flow_edge', '8f4b1a9c7d3e')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
