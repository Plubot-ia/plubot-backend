"""Add Plubot Despierto fields

Revision ID: 262da8a55bc6
Revises: 5461c7d5aa8a
Create Date: 2025-04-24 22:32:21.608528
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '262da8a55bc6'
down_revision = '5461c7d5aa8a'
branch_labels = None
depends_on = None

def upgrade():
    # Limpiar datos en powers para asegurar que sean JSON válidos
    op.execute("""
        UPDATE plubots
        SET powers = CASE
            WHEN powers IS NULL OR powers = '' THEN '[]'
            WHEN powers = 'slack' THEN '["slack"]'
            WHEN powers = 'google-sheets' THEN '["google-sheets"]'
            ELSE '["' || powers || '"]'
        END
        WHERE powers IS NOT NULL AND powers NOT LIKE '[%]'
    """)

    # Agregar nuevos campos a la tabla plubots con valores por defecto
    with op.batch_alter_table('plubots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plan_type', sa.String(), nullable=False, server_default='free'))
        batch_op.add_column(sa.Column('avatar', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('menu_options', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('response_limit', sa.Integer(), nullable=False, server_default='100'))
        batch_op.add_column(sa.Column('conversation_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('is_webchat_enabled', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.add_column(sa.Column('power_config', sa.JSON(), nullable=False, server_default='{}'))
        # Cambiar el tipo de powers a JSON con conversión explícita
        batch_op.alter_column('powers', existing_type=sa.String(), type_=sa.JSON(), postgresql_using='powers::json', existing_nullable=True)

def downgrade():
    # Revertir los cambios en la tabla plubots
    with op.batch_alter_table('plubots', schema=None) as batch_op:
        batch_op.alter_column('powers', existing_type=sa.JSON(), type_=sa.String(), existing_nullable=True)
        batch_op.drop_column('power_config')
        batch_op.drop_column('is_webchat_enabled')
        batch_op.drop_column('message_count')
        batch_op.drop_column('conversation_count')
        batch_op.drop_column('response_limit')
        batch_op.drop_column('menu_options')
        batch_op.drop_column('avatar')
        batch_op.drop_column('plan_type')