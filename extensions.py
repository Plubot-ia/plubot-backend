from __future__ import annotations

"""
Extensiones de Flask centralizadas
"""
import os

from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

# Custom metadata with naming convention
metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

# Inicializar extensiones sin app
db = SQLAlchemy(metadata=metadata)
# Force metadata refresh for WhatsApp models - 2024-08-16 14:26:00
migrate = Migrate()
jwt = JWTManager()
mail = Mail()
cors = CORS()
# La configuración de storage_uri se aplicará dinámicamente en app.py
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("REDIS_URL"),
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window",
)
