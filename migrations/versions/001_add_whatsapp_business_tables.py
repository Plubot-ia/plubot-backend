"""Add WhatsApp Business tables

Revision ID: add_whatsapp_business
Revises: 
Create Date: 2025-08-15 02:27:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_whatsapp_business'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create whatsapp_business table
    op.create_table('whatsapp_business',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plubot_id', sa.Integer(), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('waba_id', sa.String(100), nullable=True),
        sa.Column('phone_number_id', sa.String(100), nullable=True),
        sa.Column('phone_number', sa.String(20), nullable=True),
        sa.Column('business_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['plubot_id'], ['plubots.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_whatsapp_business_plubot_id'), 'whatsapp_business', ['plubot_id'], unique=True)
    op.create_index(op.f('ix_whatsapp_business_phone_number_id'), 'whatsapp_business', ['phone_number_id'], unique=False)
    
    # Create whatsapp_messages table
    op.create_table('whatsapp_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('whatsapp_business_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.String(255), nullable=True),
        sa.Column('from_number', sa.String(20), nullable=True),
        sa.Column('to_number', sa.String(20), nullable=True),
        sa.Column('message_type', sa.String(50), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('is_inbound', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('message_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['whatsapp_business_id'], ['whatsapp_business.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_whatsapp_messages_message_id'), 'whatsapp_messages', ['message_id'], unique=False)
    op.create_index(op.f('ix_whatsapp_messages_from_number'), 'whatsapp_messages', ['from_number'], unique=False)
    op.create_index(op.f('ix_whatsapp_messages_to_number'), 'whatsapp_messages', ['to_number'], unique=False)
    
    # Create whatsapp_webhook_events table
    op.create_table('whatsapp_webhook_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('whatsapp_business_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=True),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['whatsapp_business_id'], ['whatsapp_business.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_whatsapp_webhook_events_event_type'), 'whatsapp_webhook_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_whatsapp_webhook_events_created_at'), 'whatsapp_webhook_events', ['created_at'], unique=False)


def downgrade():
    # Drop tables in reverse order
    op.drop_index(op.f('ix_whatsapp_webhook_events_created_at'), table_name='whatsapp_webhook_events')
    op.drop_index(op.f('ix_whatsapp_webhook_events_event_type'), table_name='whatsapp_webhook_events')
    op.drop_table('whatsapp_webhook_events')
    
    op.drop_index(op.f('ix_whatsapp_messages_to_number'), table_name='whatsapp_messages')
    op.drop_index(op.f('ix_whatsapp_messages_from_number'), table_name='whatsapp_messages')
    op.drop_index(op.f('ix_whatsapp_messages_message_id'), table_name='whatsapp_messages')
    op.drop_table('whatsapp_messages')
    
    op.drop_index(op.f('ix_whatsapp_business_phone_number_id'), table_name='whatsapp_business')
    op.drop_index(op.f('ix_whatsapp_business_plubot_id'), table_name='whatsapp_business')
    op.drop_table('whatsapp_business')
