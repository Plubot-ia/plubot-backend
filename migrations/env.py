import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from flask import current_app

# Cargar variables de entorno desde .env
load_dotenv()

# este es el objeto de configuración de Alembic, que proporciona
# acceso a los valores dentro del archivo .ini en uso.
config = context.config

# Interpretar el archivo de configuración para el logging de Python.
# Esta línea configura básicamente los loggers.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Para el soporte de 'autogenerate', necesitamos la metadata del modelo de la app
# Para Flask-Migrate, podemos obtener esto desde la app de Flask
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

# Usar current_app para asegurar que usamos el mismo contexto que el CLI de Flask
from app import create_app, db

app = create_app()
with app.app_context():
    # Para el soporte de 'autogenerate', necesitamos la metadata del modelo de la app
    # Para Flask-Migrate, podemos obtener esto desde la app de Flask
    # Forzar la importación de todos los modelos para que Alembic los detecte
    from models import __all__  # noqa

    target_metadata = db.metadata

    # Configurar la URL de la base de datos desde la configuración de la app actual
    db_url = app.config.get('SQLALCHEMY_DATABASE_URI')
    if os.getenv('DATABASE_URL'):
        db_url = os.getenv('DATABASE_URL')
    config.set_main_option("sqlalchemy.url", db_url)

def run_migrations_offline() -> None:
    """Ejecuta las migraciones en modo 'offline'."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Ejecuta las migraciones en modo 'online'."""
        # connectable = db.engine # Original
    connectable = context.config.attributes.get("connection", None)

    if connectable is None:
        # only create Engine if we don't have a Connection
        # from the outside
        connectable = db.engine

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()