"""Add new fields to Plubot for Despierto

Revision ID: 9439960470ad
Revises: 262da8a55bc6
Create Date: 2025-04-24 23:14:02.567691
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9439960470ad'
down_revision = '262da8a55bc6'
branch_labels = None
depends_on = None

def upgrade():
    # Asegurar que los campos existentes sean nullable
    op.alter_column('plubots', 'plan_type', existing_type=sa.VARCHAR(), nullable=True, existing_server_default=sa.text("'free'::character varying"))
    op.alter_column('plubots', 'menu_options', existing_type=postgresql.JSON(astext_type=sa.Text()), nullable=True, existing_server_default=sa.text("'[]'::json"))
    op.alter_column('plubots', 'response_limit', existing_type=sa.INTEGER(), nullable=True, existing_server_default=sa.text('100'))
    op.alter_column('plubots', 'conversation_count', existing_type=sa.INTEGER(), nullable=True, existing_server_default=sa.text('0'))
    op.alter_column('plubots', 'message_count', existing_type=sa.INTEGER(), nullable=True, existing_server_default=sa.text('0'))
    op.alter_column('plubots', 'is_webchat_enabled', existing_type=sa.BOOLEAN(), nullable=True, existing_server_default=sa.text('true'))
    op.alter_column('plubots', 'power_config', existing_type=postgresql.JSON(astext_type=sa.Text()), nullable=True, existing_server_default=sa.text("'{}'::json"))

def downgrade():
    # Revertir cambios
    op.alter_column('plubots', 'power_config', existing_type=postgresql.JSON(astext_type=sa.Text()), nullable=False, existing_server_default=sa.text("'{}'::json"))
    op.alter_column('plubots', 'is_webchat_enabled', existing_type=sa.BOOLEAN(), nullable=False, existing_server_default=sa.text('true'))
    op.alter_column('plubots', 'message_count', existing_type=sa.INTEGER(), nullable=False, existing_server_default=sa.text('0'))
    op.alter_column('plubots', 'conversation_count', existing_type=sa.INTEGER(), nullable=False, existing_server_default=sa.text('0'))
    op.alter_column('plubots', 'response_limit', existing_type=sa.INTEGER(), nullable=False, existing_server_default=sa.text('100'))
    op.alter_column('plubots', 'menu_options', existing_type=postgresql.JSON(astext_type=sa.Text()), nullable=False, existing_server_default=sa.text("'[]'::json"))
    op.alter_column('plubots', 'plan_type', existing_type=sa.VARCHAR(), nullable=False, existing_server_default=sa.text("'free'::character varying"))