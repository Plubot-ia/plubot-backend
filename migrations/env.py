from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

# Importar modelos para que Alembic los detecte
from models import Base, User, Plubot, Conversation, Flow, FlowEdge, Template, MessageQuota

# Cargar la configuración de Alembic
config = context.config

# Configurar el logging desde el archivo ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL de la base de datos para PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://plubot_db_user:K8bDdaMaPVWGV6WFidXskFmkvJ579KH2@dpg-cvqulmmuk2gs73c2ea00-a.oregon-postgres.render.com/plubot_db')
config.set_main_option('sqlalchemy.url', DATABASE_URL)

# Conectar a la base de datos
connectable = engine_from_config(
    config.get_section(config.config_ini_section),
    prefix='sqlalchemy.',
    poolclass=pool.NullPool)

# Ejecutar migraciones
with connectable.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata
    )

    with context.begin_transaction():
        context.run_migrations()