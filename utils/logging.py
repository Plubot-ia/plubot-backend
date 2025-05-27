import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """
    Configura el sistema de logging para la aplicación con archivo rotativo y salida a consola.
    """
    # Crear formateador
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Configurar handler para archivo con rotación
    file_handler = RotatingFileHandler(
        'plubot.log',
        maxBytes=1_000_000,  # 1 MB por archivo
        backupCount=5        # Mantener hasta 5 archivos de respaldo
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Configurar handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Configurar logger raíz
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Sistema de logging configurado correctamente")
    return logger