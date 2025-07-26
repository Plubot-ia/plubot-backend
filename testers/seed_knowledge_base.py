"""Script para inicializar la base de datos de conocimiento con datos sobre Plubot."""

import logging

import requests

# --- Configuración del Logger ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Constantes ---
BULK_ADD_URL = "http://localhost:5000/api/knowledge/bulk-add"
REQUEST_TIMEOUT = 10  # segundos

# --- Base de Conocimiento ---
PLUBOT_KNOWLEDGE = [
    {
        "category": "general",
        "question": "¿Qué es Plubot?",
        "answer": (
            "Plubot es una plataforma para crear asistentes digitales personalizados "
            "sin necesidad de programación. Te permite diseñar flujos de conversación "
            "intuitivos para chatbots y automatizar interacciones."
        ),
        "keywords": "plubot, plataforma, asistente, digital, chatbot, qué es, definición",
    },
    {
        "category": "general",
        "question": "¿Para qué sirve Plubot?",
        "answer": (
            "Plubot sirve para crear asistentes virtuales personalizados para atención "
            "al cliente, soporte técnico, ventas, educación y cualquier caso de uso "
            "conversacional sin necesidad de programar."
        ),
        "keywords": "sirve, uso, función, propósito, objetivo, utilidad",
    },
    {
        "category": "general",
        "question": "¿Cómo funciona Plubot?",
        "answer": (
            "Plubot funciona mediante un editor visual donde diseñas flujos de "
            "conversación conectando nodos. Cada nodo representa un paso en la "
            "interacción con el usuario, facilitando la creación de experiencias "
            "conversacionales complejas."
        ),
        "keywords": "funciona, funcionamiento, cómo, proceso, mecánica",
    },
    {
        "category": "características",
        "question": "¿Cuáles son las características principales de Plubot?",
        "answer": (
            "Plubot ofrece un editor visual de flujos, integraciones con APIs, "
            "personalización de respuestas, análisis de conversaciones y despliegue "
            "multiplataforma sin necesidad de código."
        ),
        "keywords": "características, funciones, principales, ventajas, beneficios",
    },
    {
        "category": "características",
        "question": "¿Plubot utiliza inteligencia artificial?",
        "answer": (
            "Sí, Plubot incorpora IA para el procesamiento del lenguaje natural y la "
            "generación de respuestas contextuales, permitiendo crear asistentes "
            "más inteligentes y adaptables."
        ),
        "keywords": "IA, inteligencia artificial, NLP, machine learning, procesamiento lenguaje",
    },
    {
        "category": "características",
        "question": "¿Con qué plataformas se integra Plubot?",
        "answer": (
            "Plubot se integra con WhatsApp, Telegram, Facebook Messenger, sitios web, "
            "APIs personalizadas y sistemas CRM, ofreciendo una experiencia omnicanal."
        ),
        "keywords": "integración, plataformas, canales, conexión, omnicanal, whatsapp, telegram",
    },
    {
        "category": "tutorial",
        "question": "¿Cómo crear mi primer asistente en Plubot?",
        "answer": (
            "Para crear tu primer asistente, registra una cuenta, selecciona 'Nuevo "
            "proyecto', elige una plantilla o comienza desde cero, diseña el flujo y "
            "conecta los nodos de conversación según tu caso de uso."
        ),
        "keywords": "crear, primeros pasos, comenzar, inicio, tutorial, primer asistente",
    },
    {
        "category": "tutorial",
        "question": "¿Qué son los nodos en Plubot?",
        "answer": (
            "Los nodos son los bloques básicos para construir conversaciones en Plubot. "
            "Cada nodo representa una acción como enviar mensajes, recibir respuestas "
            "o tomar decisiones según condiciones."
        ),
        "keywords": "nodos, bloques, elementos, componentes, estructura",
    },
    {
        "category": "tutorial",
        "question": "¿Cómo puedo probar mi asistente antes de publicarlo?",
        "answer": (
            "Puedes probar tu asistente usando el simulador integrado en Plubot, que "
            "permite interactuar con él como si fueras un usuario final, detectando "
            "y corrigiendo problemas antes de su lanzamiento."
        ),
        "keywords": "probar, testing, simulador, pruebas, antes de publicar",
    },
    {
        "category": "planes",
        "question": "¿Qué planes ofrece Plubot?",
        "answer": (
            "Plubot ofrece planes gratuitos con funciones básicas y planes de "
            "suscripción (Pro, Enterprise) con características avanzadas como "
            "integraciones premium y soporte prioritario."
        ),
        "keywords": "planes, precios, suscripción, costo, pro, enterprise",
    },
    {
        "category": "planes",
        "question": "¿Hay un plan gratuito?",
        "answer": (
            "Sí, Plubot tiene un plan gratuito que te permite crear y probar "
            "asistentes con funcionalidades esenciales. Es ideal para empezar a "
            "explorar la plataforma."
        ),
        "keywords": "gratis, plan gratuito, free, sin costo",
    },
    {
        "category": "planes",
        "question": "¿Qué ofrece el plan Enterprise?",
        "answer": (
            "El plan Enterprise está diseñado para grandes empresas y ofrece "
            "soluciones a medida, soporte dedicado, SLAs (Acuerdos de Nivel de "
            "Servicio) y funciones de seguridad avanzadas."
        ),
        "keywords": "empresarial, enterprise, plan premium, alto volumen, corporativo",
    },
    {
        "category": "soporte",
        "question": "¿Cómo puedo obtener ayuda con Plubot?",
        "answer": (
            "Puedes consultar nuestra documentación, unirte a la comunidad en Discord "
            "o contactar a nuestro equipo de soporte a través del chat en la "
            "plataforma o por correo electrónico."
        ),
        "keywords": "soporte, ayuda, contacto, documentación, comunidad, discord",
    },
    {
        "category": "soporte",
        "question": "¿Ofrecen tutoriales o guías?",
        "answer": (
            "Sí, tenemos una sección de tutoriales en video y guías paso a paso en "
            "nuestra base de conocimiento para ayudarte a sacar el máximo provecho de Plubot."
        ),
        "keywords": "tutoriales, guías, documentación, videos, aprender",
    },
    {
        "category": "soporte",
        "question": "¿Qué es la comunidad de Plubot?",
        "answer": (
            "Es un espacio en Discord donde los usuarios pueden compartir "
            "conocimientos, resolver dudas, mostrar sus creaciones y recibir "
            "anuncios oficiales del equipo de Plubot."
        ),
        "keywords": "comunidad, discord, foro, usuarios, ayuda mutua",
    },
    {
        "category": "casos_uso",
        "question": "¿Para qué tipo de negocios es útil Plubot?",
        "answer": (
            "Plubot es útil para e-commerce, agencias de marketing, instituciones "
            "educativas, empresas de software y cualquier negocio que busque mejorar "
            "la comunicación con sus clientes."
        ),
        "keywords": "negocios, empresas, industrias, sectores, casos de uso",
    },
    {
        "category": "casos_uso",
        "question": "¿Puedo usar Plubot para automatizar ventas?",
        "answer": (
            "Sí, puedes diseñar flujos que califiquen leads, muestren productos, "
            "respondan preguntas frecuentes sobre precios y guíen a los usuarios "
            "hacia la compra."
        ),
        "keywords": "ventas, automatización, e-commerce, leads, calificar",
    },
    {
        "category": "casos_uso",
        "question": "¿Necesito saber programar para usar Plubot?",
        "answer": (
            "No, Plubot está diseñado para ser una plataforma sin código (no-code). "
            "Su interfaz visual te permite crear asistentes complejos sin escribir "
            "una sola línea de código."
        ),
        "keywords": "programar, código, desarrollo, técnico, sin código, no-code",
    },
    {
        "category": "tecnico",
        "question": "¿Cómo puedo conectar Plubot con mi base de datos?",
        "answer": (
            "Puedes usar el nodo de 'Acción' para hacer peticiones HTTP a tu API, que "
            "a su vez se conecta con tu base de datos para leer o escribir información."
        ),
        "keywords": "base de datos, API, HTTP, conectar, leer, escribir",
    },
    {
        "category": "tecnico",
        "question": "¿Plubot es seguro?",
        "answer": (
            "Sí, la seguridad es una prioridad. Utilizamos encriptación para los "
            "datos en tránsito y en reposo, y seguimos las mejores prácticas de la "
            "industria para proteger tu información."
        ),
        "keywords": "seguridad, encriptación, protección, datos, privacidad",
    },
    {
        "category": "tecnico",
        "question": "¿Qué es el Pluniverse?",
        "answer": (
            "El Pluniverse es el ecosistema digital de Plubot. Es un mapa "
            "interactivo donde puedes acceder a la Fábrica de Bots, el Marketplace "
            "de Extensiones y otras zonas."
        ),
        "keywords": "pluniverse, mapa, universo, ciudad digital, zonas",
    },
    {
        "category": "poderes",
        "question": "¿Qué son los poderes de Plubot?",
        "answer": (
            "Son habilidades o integraciones que puedes activar en tu Plubot, como "
            "enviar mensajes por WhatsApp, cobrar con Stripe o automatizar flujos avanzados."
        ),
        "keywords": "poderes, integraciones, habilidades, whatsapp, stripe",
    },
    {
        "category": "poderes",
        "question": "¿Cómo desbloqueo un poder?",
        "answer": (
            "Los poderes se desbloquean desde el Marketplace de Extensiones en el "
            "Pluniverse. Algunos son gratuitos y otros requieren suscripción o pago único."
        ),
        "keywords": "desbloquear, poderes, marketplace, extensiones",
    },
    {
        "category": "planes",
        "question": "¿Plubot es gratuito?",
        "answer": (
            "Sí. Puedes crear un Plubot gratuito con funciones básicas. Para agregar "
            "integraciones y automatizaciones avanzadas puedes subir de plan."
        ),
        "keywords": "plan gratuito, gratis, costos, suscripción",
    },
    {
        "category": "planes",
        "question": "¿Qué incluye el plan Pro?",
        "answer": (
            "Acceso a todas las integraciones, flujos ilimitados, analíticas "
            "avanzadas, marca blanca y prioridad de soporte."
        ),
        "keywords": "plan pro, premium, funciones, integraciones",
    },
    {
        "category": "creacion_bots",
        "question": "¿Cómo creo mi Plubot?",
        "answer": (
            "Desde la Fábrica de Bots en el Pluniverse. Allí eliges nombre, "
            "personalidad, habilidades y puedes agregarle poderes desde el Marketplace."
        ),
        "keywords": "crear plubot, asistente, fábrica de bots",
    },
    {
        "category": "creacion_bots",
        "question": "¿Qué personalidades puedo elegir?",
        "answer": "Formal, amigable, motivacional, sabio y futurista. Próximamente más opciones.",
        "keywords": "personalidad, tipos, estilo bot",
    },
    {
        "category": "flujos_nodos",
        "question": "¿Qué es un flujo de nodos?",
        "answer": (
            "Es un diagrama visual donde conectas bloques como mensajes, decisiones y "
            "acciones para automatizar respuestas y tareas."
        ),
        "keywords": "flujo, nodos, automatización, diagrama",
    },
    {
        "category": "flujos_nodos",
        "question": "¿Cuáles nodos puedo usar?",
        "answer": (
            "Mensaje, Decisión, Acción, Espera, Inicio y Final. Puedes combinarlos "
            "para crear flujos conversacionales inteligentes."
        ),
        "keywords": "nodos, tipos, flujo, bot",
    },
    {
        "category": "integraciones",
        "question": "¿Con qué herramientas se puede conectar Plubot?",
        "answer": (
            "Con WhatsApp, Instagram, Stripe, MercadoPago, Notion, Trello, Mailchimp, "
            "Google Sheets y más."
        ),
        "keywords": "integraciones, apps, whatsapp, stripe",
    },
    {
        "category": "integraciones",
        "question": "¿Cómo conecto WhatsApp a Plubot?",
        "answer": (
            "Desde el Marketplace, desbloquea el poder de WhatsApp y sigue las "
            "instrucciones para vincular tu cuenta empresarial vía Twilio o 360dialog."
        ),
        "keywords": "conectar whatsapp, poder, integración",
    },
]


def load_knowledge_to_plubot() -> bool:
    """Carga el conocimiento sobre Plubot a la base de datos.

    Returns:
        bool: True si la carga fue exitosa, False en caso contrario.
    """
    try:
        payload = {"items": PLUBOT_KNOWLEDGE}
        response = requests.post(
            BULK_ADD_URL, json=payload, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()  # Lanza una excepción para errores HTTP (4xx o 5xx)
    except requests.RequestException:
        logger.exception("Error de red al cargar el conocimiento")
        return False
    else:
        result = response.json()
        logger.info("Éxito: %s", result.get("message", "Operación completada."))
        return True


if __name__ == "__main__":
    logger.info("Cargando base de conocimiento para Byte Embajador...")
    if load_knowledge_to_plubot():
        logger.info("La base de conocimiento se ha cargado exitosamente.")
    else:
        logger.error("Hubo un problema al cargar la base de conocimiento.")
