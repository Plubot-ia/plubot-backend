#!/usr/bin/env python3
"""Script para ejecutar migraciones con el contexto de la aplicación"""
import os
os.environ['DATABASE_URL'] = 'postgresql://plubot_db_user:K8bDdaMaPVWGV6WFidXskFmkvJ579KH2@dpg-cvqulmmuk2gs73c2ea00-a.oregon-postgres.render.com/plubot_db'

from app import create_app
from flask_migrate import upgrade

app = create_app()

with app.app_context():
    upgrade()
    print("Migraciones ejecutadas exitosamente")
