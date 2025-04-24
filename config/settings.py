import os
from dotenv import load_dotenv
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# Cargar el archivo .env desde la carpeta "instance"
dotenv_path = os.path.join(os.path.dirname(__file__), '../instance/.env')
load_dotenv(dotenv_path)

# Depuración para verificar que se carga la URL de la base
print("DATABASE_URL desde settings.py:", os.getenv('DATABASE_URL'))

def load_config(app):
    """
    Carga las configuraciones de la aplicación desde variables de entorno y las aplica a Flask.
    """
    # Configuraciones de Flask
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    if not app.config['SECRET_KEY']:
        raise ValueError("No se encontró SECRET_KEY en las variables de entorno.")

    # Configuración de la base de datos para SQLAlchemy
    database_url = os.getenv('DATABASE_URL', '').replace('postgres://', 'postgresql://')
    if not database_url:
        raise ValueError("No se encontró DATABASE_URL en las variables de entorno.")
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DATABASE_URL'] = database_url

    app.config['REDIS_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # Configuraciones de JWT
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['JWT_TOKEN_LOCATION'] = ['cookies', 'headers']  # Cambiado
    app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False
    app.config['JWT_COOKIE_SECURE'] = os.getenv('FLASK_ENV', 'development') != 'development'
    app.config['JWT_COOKIE_SAMESITE'] = 'None' if os.getenv('FLASK_ENV') != 'development' else 'Lax'
    app.config['JWT_ACCESS_COOKIE_PATH'] = '/'

    # Configuraciones de Flask-Mail
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

    # Configuraciones de API
    app.config['XAI_API_KEY'] = os.getenv('XAI_API_KEY')
    if not app.config['XAI_API_KEY']:
        raise ValueError("No se encontró XAI_API_KEY en las variables de entorno.")

    app.config['TWILIO_SID'] = os.getenv('TWILIO_SID')
    app.config['TWILIO_TOKEN'] = os.getenv('TWILIO_TOKEN')
    app.config['TWILIO_PHONE'] = os.getenv('TWILIO_PHONE')
    if not all([app.config['TWILIO_SID'], app.config['TWILIO_TOKEN'], app.config['TWILIO_PHONE']]):
        raise ValueError("Faltan credenciales de Twilio en las variables de entorno.")

    # Configuración de la clave de encriptación
    app.config['ENCRYPTION_KEY'] = os.getenv('ENCRYPTION_KEY')
    if not app.config['ENCRYPTION_KEY']:
        raise ValueError("No se encontró ENCRYPTION_KEY en las variables de entorno.")

# Configuración de SQLAlchemy
database_url = os.getenv('DATABASE_URL', '').replace('postgres://', 'postgresql://')
if not database_url:
    raise ValueError("DATABASE_URL no está definido correctamente en el entorno.")
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)

@contextmanager
def get_session():
    """
    Provee una sesión de SQLAlchemy con manejo automático de commit/rollback.
    """
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()