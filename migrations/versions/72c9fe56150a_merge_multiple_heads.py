"""merge multiple heads

Revision ID: 72c9fe56150a
Revises: add_all_missing_columns, add_google_auth_columns, e8ed9f25a727
Create Date: 2025-05-18 01:38:36.962720

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '72c9fe56150a'
down_revision = ('add_all_missing_columns', 'add_google_auth_columns', 'e8ed9f25a727')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
