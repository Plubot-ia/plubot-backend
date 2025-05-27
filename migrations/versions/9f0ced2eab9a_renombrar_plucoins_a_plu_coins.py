from alembic import op
import sqlalchemy as sa

# Identificadores de la migración
revision = '9f0ced2eab9a'
down_revision = '63442b7e59c0'

def upgrade():
    # Verificar si la columna plucoins existe antes de renombrar
    inspector = sa.inspect(op.get_bind())
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'plucoins' in columns:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.alter_column('plucoins', new_column_name='plu_coins')
    else:
        # Si no existe, crear la columna plu_coins directamente
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('plu_coins', sa.Integer(), nullable=True, server_default='0'))

def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'plu_coins' in columns:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.alter_column('plu_coins', new_column_name='plucoins')
    else:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('plu_coins')