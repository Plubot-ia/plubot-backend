"""Rename chatbots table to plubots and update foreign keys

Revision ID: c40730c60218
Revises: d924d76d7f78
Create Date: 2025-04-23 20:59:18.678

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c40730c60218'
down_revision = 'd924d76d7f78'
branch_labels = None
depends_on = None

def upgrade():
    # Renombrar la tabla chatbots a plubots
    op.rename_table('chatbots', 'plubots')

    # Renombrar las claves foráneas para que apunten a la nueva tabla plubots
    # Primero eliminamos las claves foráneas existentes
    op.drop_constraint('conversations_chatbot_id_fkey', 'conversations', type_='foreignkey')
    op.drop_constraint('flows_chatbot_id_fkey', 'flows', type_='foreignkey')
    op.drop_constraint('flow_edges_chatbot_id_fkey', 'flow_edges', type_='foreignkey')

    # Creamos nuevas claves foráneas que apunten a plubots.id
    op.create_foreign_key('conversations_chatbot_id_fkey', 'conversations', 'plubots', ['chatbot_id'], ['id'])
    op.create_foreign_key('flows_chatbot_id_fkey', 'flows', 'plubots', ['chatbot_id'], ['id'])
    op.create_foreign_key('flow_edges_chatbot_id_fkey', 'flow_edges', 'plubots', ['chatbot_id'], ['id'])

def downgrade():
    # Revertir los cambios: renombrar plubots a chatbots
    # Primero eliminamos las claves foráneas actuales
    op.drop_constraint('conversations_chatbot_id_fkey', 'conversations', type_='foreignkey')
    op.drop_constraint('flows_chatbot_id_fkey', 'flows', type_='foreignkey')
    op.drop_constraint('flow_edges_chatbot_id_fkey', 'flow_edges', type_='foreignkey')

    # Renombrar la tabla de vuelta a chatbots
    op.rename_table('plubots', 'chatbots')

    # Restaurar las claves foráneas apuntando a chatbots.id
    op.create_foreign_key('conversations_chatbot_id_fkey', 'conversations', 'chatbots', ['chatbot_id'], ['id'])
    op.create_foreign_key('flows_chatbot_id_fkey', 'flows', 'chatbots', ['chatbot_id'], ['id'])
    op.create_foreign_key('flow_edges_chatbot_id_fkey', 'flow_edges', 'chatbots', ['chatbot_id'], ['id'])