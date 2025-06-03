"""add_animated_to_flow_edges

Revision ID: 3effa7a00566
Revises: e3533f093a7a
Create Date: 2025-06-03 05:57:20.273899

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3effa7a00566'
down_revision = 'e3533f093a7a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('flow_edges',
                  sa.Column('animated', sa.Boolean(), nullable=False, server_default=sa.text('TRUE'))
                  )
    # Para las filas existentes donde 'animated' sería NULL después de añadir la columna (si no tuviera server_default),
    # y antes de establecer nullable=False, podríamos necesitar una actualización explícita.
    # Sin embargo, server_default=sa.text('TRUE') debería manejar esto para la mayoría de las bases de datos al crear la columna.
    # Si la base de datos no aplica el server_default a filas existentes inmediatamente (raro para adiciones de columnas con default),
    # podríamos necesitar: op.execute('UPDATE flow_edges SET animated = TRUE WHERE animated IS NULL')
    # Pero con nullable=False y server_default, esto usualmente no es necesario.


def downgrade():
    op.drop_column('flow_edges', 'animated')
