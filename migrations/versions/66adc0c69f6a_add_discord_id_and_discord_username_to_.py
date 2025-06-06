"""Add discord_id and discord_username to User model

Revision ID: 66adc0c69f6a
Revises: 3effa7a00566
Create Date: 2025-06-03 19:03:35.916554

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '66adc0c69f6a'
down_revision = '3effa7a00566'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('flow_edges', 'edge_type',
               existing_type=sa.VARCHAR(length=50),
               nullable=True,
               existing_server_default=sa.text("'default'::character varying"))
    op.drop_index('idx_flow_edge_frontend_id', table_name='flow_edges')
    op.create_index('idx_flow_edge_frontend_id', 'flow_edges', ['chatbot_id', 'frontend_id'], unique=False)
    op.create_index('idx_flow_edge_chatbot', 'flow_edges', ['chatbot_id'], unique=False)
    op.create_index('idx_flow_edge_source_target', 'flow_edges', ['chatbot_id', 'source_flow_id', 'target_flow_id'], unique=False)
    op.create_index(op.f('ix_flow_edges_frontend_id'), 'flow_edges', ['frontend_id'], unique=False)
    op.drop_constraint('flow_edges_chatbot_id_fkey', 'flow_edges', type_='foreignkey')
    op.create_foreign_key(None, 'flow_edges', 'plubots', ['chatbot_id'], ['id'], ondelete='CASCADE')
    op.drop_index('idx_flow_frontend_id', table_name='flows')
    op.create_index('idx_flow_chatbot_frontend', 'flows', ['chatbot_id', 'frontend_id'], unique=False)
    op.create_index('idx_flow_coordinates', 'flows', ['chatbot_id', 'position_x', 'position_y'], unique=False)
    op.create_index('idx_flow_position', 'flows', ['chatbot_id', 'position'], unique=False)
    op.create_index(op.f('ix_flows_frontend_id'), 'flows', ['frontend_id'], unique=False)
    op.drop_constraint('flows_chatbot_id_fkey', 'flows', type_='foreignkey')
    op.create_foreign_key(None, 'flows', 'plubots', ['chatbot_id'], ['id'], ondelete='CASCADE')
    op.add_column('users', sa.Column('discord_id', sa.String(), nullable=True))
    op.add_column('users', sa.Column('discord_username', sa.String(), nullable=True))
    op.drop_index('ix_users_google_id', table_name='users')
    op.create_unique_constraint(None, 'users', ['google_id'])
    op.create_unique_constraint(None, 'users', ['discord_id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_constraint(None, 'users', type_='unique')
    op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)
    op.drop_column('users', 'discord_username')
    op.drop_column('users', 'discord_id')
    op.drop_constraint(None, 'flows', type_='foreignkey')
    op.create_foreign_key('flows_chatbot_id_fkey', 'flows', 'plubots', ['chatbot_id'], ['id'])
    op.drop_index(op.f('ix_flows_frontend_id'), table_name='flows')
    op.drop_index('idx_flow_position', table_name='flows')
    op.drop_index('idx_flow_coordinates', table_name='flows')
    op.drop_index('idx_flow_chatbot_frontend', table_name='flows')
    op.create_index('idx_flow_frontend_id', 'flows', ['frontend_id'], unique=False)
    op.drop_constraint(None, 'flow_edges', type_='foreignkey')
    op.create_foreign_key('flow_edges_chatbot_id_fkey', 'flow_edges', 'plubots', ['chatbot_id'], ['id'])
    op.drop_index(op.f('ix_flow_edges_frontend_id'), table_name='flow_edges')
    op.drop_index('idx_flow_edge_source_target', table_name='flow_edges')
    op.drop_index('idx_flow_edge_chatbot', table_name='flow_edges')
    op.drop_index('idx_flow_edge_frontend_id', table_name='flow_edges')
    op.create_index('idx_flow_edge_frontend_id', 'flow_edges', ['frontend_id'], unique=False)
    op.alter_column('flow_edges', 'edge_type',
               existing_type=sa.VARCHAR(length=50),
               nullable=False,
               existing_server_default=sa.text("'default'::character varying"))
    # ### end Alembic commands ###
