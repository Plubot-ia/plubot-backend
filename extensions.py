from __future__ import annotations

import os

from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
mail = Mail()
# La configuración de storage_uri se aplicará dinámicamente en app.py
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("REDIS_URL"),
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window",
)
