# plubot-backend/seed_knowledge_base.py
import json
import requests

# URL del endpoint para carga masiva
BULK_ADD_URL = "http://localhost:5000/api/knowledge/bulk-add"  # Ajusta la URL según tu configuración

# Conocimiento sobre Plubot
plubot_knowledge = [
    {
        "category": "general",
        "question": "¿Qué es Plubot?",
        "answer": "Plubot es una plataforma para crear asistentes digitales personalizados sin necesidad de programación. Te permite diseñar flujos de conversación intuitivos para chatbots y automatizar interacciones.",
        "keywords": "plubot, plataforma, asistente, digital, chatbot, qué es, definición"
    },
    {
        "category": "general",
        "question": "¿Para qué sirve Plubot?",
        "answer": "Plubot sirve para crear asistentes virtuales personalizados para atención al cliente, soporte técnico, ventas, educación y cualquier caso de uso conversacional sin necesidad de programar.",
        "keywords": "sirve, uso, función, propósito, objetivo, utilidad"
    },
    {
        "category": "general",
        "question": "¿Cómo funciona Plubot?",
        "answer": "Plubot funciona mediante un editor visual donde diseñas flujos de conversación conectando nodos. Cada nodo representa un paso en la interacción con el usuario, facilitando la creación de experiencias conversacionales complejas.",
        "keywords": "funciona, funcionamiento, cómo, proceso, mecánica"
    },
    {
        "category": "características",
        "question": "¿Cuáles son las características principales de Plubot?",
        "answer": "Plubot ofrece un editor visual de flujos, integraciones con APIs, personalización de respuestas, análisis de conversaciones y despliegue multiplataforma sin necesidad de código.",
        "keywords": "características, funciones, principales, ventajas, beneficios"
    },
    {
        "category": "características",
        "question": "¿Plubot utiliza inteligencia artificial?",
        "answer": "Sí, Plubot incorpora IA para el procesamiento del lenguaje natural y la generación de respuestas contextuales, permitiendo crear asistentes más inteligentes y adaptables.",
        "keywords": "IA, inteligencia artificial, NLP, machine learning, procesamiento lenguaje"
    },
    {
        "category": "características",
        "question": "¿Con qué plataformas se integra Plubot?",
        "answer": "Plubot se integra con WhatsApp, Telegram, Facebook Messenger, sitios web, APIs personalizadas y sistemas CRM, ofreciendo una experiencia omnicanal.",
        "keywords": "integración, plataformas, canales, conexión, omnicanal, whatsapp, telegram"
    },
    {
        "category": "tutorial",
        "question": "¿Cómo crear mi primer asistente en Plubot?",
        "answer": "Para crear tu primer asistente, registra una cuenta, selecciona 'Nuevo proyecto', elige una plantilla o comienza desde cero, diseña el flujo y conecta los nodos de conversación según tu caso de uso.",
        "keywords": "crear, primeros pasos, comenzar, inicio, tutorial, primer asistente"
    },
    {
        "category": "tutorial",
        "question": "¿Qué son los nodos en Plubot?",
        "answer": "Los nodos son los bloques básicos para construir conversaciones en Plubot. Cada nodo representa una acción como enviar mensajes, recibir respuestas o tomar decisiones según condiciones.",
        "keywords": "nodos, bloques, elementos, componentes, estructura"
    },
    {
        "category": "tutorial",
        "question": "¿Cómo puedo probar mi asistente antes de publicarlo?",
        "answer": "Puedes probar tu asistente usando el simulador integrado en Plubot, que permite interactuar con él como si fueras un usuario final, detectando y corrigiendo problemas antes de su lanzamiento.",
        "keywords": "probar, testing, simulador, pruebas, antes de publicar"
    },
    {
        "category": "planes",
        "question": "¿Qué planes ofrece Plubot?",
        "answer": "Plubot ofrece un plan gratuito con funcionalidades básicas, y planes de pago (Básico, Profesional y Empresarial) con capacidades avanzadas, más conversaciones y mejor soporte.",
        "keywords": "planes, precios, costos, tarifas, suscripción"
    },
    {
        "category": "planes",
        "question": "¿Existe una versión gratuita de Plubot?",
        "answer": "Sí, Plubot ofrece un plan gratuito que te permite crear asistentes básicos con límites en el número de conversaciones mensuales y funciones avanzadas.",
        "keywords": "gratuito, gratis, free, plan gratis, versión gratuita"
    },
    {
        "category": "planes",
        "question": "¿Qué incluye el plan Empresarial de Plubot?",
        "answer": "El plan Empresarial incluye conversaciones ilimitadas, integraciones personalizadas, soporte dedicado, capacitación, analíticas avanzadas y posibilidad de implementación on-premise.",
        "keywords": "empresarial, enterprise, plan premium, alto volumen, corporativo"
    },
    {
        "category": "soporte",
        "question": "¿Cómo puedo obtener ayuda con Plubot?",
        "answer": "Puedes obtener ayuda a través de la documentación en línea, tutoriales en video, comunidad de usuarios, y soporte por correo o chat según tu plan de suscripción.",
        "keywords": "ayuda, soporte, asistencia, problemas, dudas, contacto"
    },
    {
        "category": "soporte",
        "question": "¿Ofrecen capacitación para usar Plubot?",
        "answer": "Sí, Plubot ofrece webinars gratuitos, tutoriales en video y sesiones de capacitación personalizadas para planes Profesional y Empresarial.",
        "keywords": "capacitación, entrenamiento, formación, aprender, webinar, cursos"
    },
    {
        "category": "casos_uso",
        "question": "¿Para qué tipos de negocios es útil Plubot?",
        "answer": "Plubot es útil para todo tipo de negocios: retail, servicios financieros, educación, salud, turismo, o cualquier empresa que busque automatizar conversaciones y mejorar la atención al cliente.",
        "keywords": "negocios, empresas, industrias, sectores, casos de uso"
    },
    {
        "category": "casos_uso",
        "question": "¿Puedo usar Plubot para automatizar ventas?",
        "answer": "Sí, Plubot es ideal para automatizar ventas mediante flujos que califican leads, responden preguntas sobre productos, muestran catálogos y procesan pedidos directamente desde la conversación.",
        "keywords": "ventas, automatizar ventas, leads, conversión, comercio"
    },
    {
        "category": "casos_uso",
        "question": "¿Cómo puedo usar Plubot para atención al cliente?",
        "answer": "Con Plubot puedes crear asistentes que resuelvan dudas frecuentes, gestionen tickets de soporte, escalen a agentes humanos cuando sea necesario y funcionen 24/7.",
        "keywords": "atención cliente, soporte, servicio cliente, helpdesk, customer service"
    },
    {
        "category": "tecnico",
        "question": "¿Necesito saber programar para usar Plubot?",
        "answer": "No, Plubot está diseñado para ser usado sin conocimientos de programación gracias a su interfaz visual. Para funciones avanzadas, puedes usar integración con APIs si tienes conocimientos técnicos.",
        "keywords": "programar, código, desarrollo, técnico, sin código, no-code"
    },
    {
        "category": "tecnico",
        "question": "¿Cómo puedo conectar Plubot con mi base de datos?",
        "answer": "Puedes conectar Plubot con tu base de datos mediante la integración con APIs, webhooks o utilizando conectores específicos disponibles en planes avanzados.",
        "keywords": "base datos, database, conexión, integración, datos externos"
    },
    {
        "category": "tecnico",
        "question": "¿Es seguro Plubot para datos sensibles?",
        "answer": "Sí, Plubot cumple con estándares de seguridad como encriptación de datos, autenticación de dos factores y políticas de protección de datos según regulaciones como GDPR.",
        "keywords": "seguridad, privacidad, datos sensibles, protección, encriptación"
    },
    {
        "category": "general",
        "question": "¿Qué es el Pluniverse?",
        "answer": "El Pluniverse es el universo digital de Plubot. Una ciudad flotante donde cada zona representa una función: creación de bots, personalización, integraciones y comunidad.",
        "keywords": "pluniverse, mapa, universo, ciudad digital, zonas"
    },
    {
        "category": "poderes",
        "question": "¿Qué son los poderes de Plubot?",
        "answer": "Son habilidades o integraciones que puedes activar en tu Plubot, como enviar mensajes por WhatsApp, cobrar con Stripe o automatizar flujos avanzados.",
        "keywords": "poderes, integraciones, habilidades, whatsapp, stripe"
    },
    {
        "category": "poderes",
        "question": "¿Cómo desbloqueo un poder?",
        "answer": "Los poderes se desbloquean desde el Marketplace de Extensiones en el Pluniverse. Algunos son gratuitos y otros requieren suscripción o pago único.",
        "keywords": "desbloquear, poderes, marketplace, extensiones"
    },
    {
        "category": "planes",
        "question": "¿Plubot es gratuito?",
        "answer": "Sí. Puedes crear un Plubot gratuito con funciones básicas. Para agregar integraciones y automatizaciones avanzadas puedes subir de plan.",
        "keywords": "plan gratuito, gratis, costos, suscripción"
    },
    {
        "category": "planes",
        "question": "¿Qué incluye el plan Pro?",
        "answer": "Acceso a todas las integraciones, flujos ilimitados, analíticas avanzadas, marca blanca y prioridad de soporte.",
        "keywords": "plan pro, premium, funciones, integraciones"
    },
    {
        "category": "creacion_bots",
        "question": "¿Cómo creo mi Plubot?",
        "answer": "Desde la Fábrica de Bots en el Pluniverse. Allí eliges nombre, personalidad, habilidades y puedes agregarle poderes desde el Marketplace.",
        "keywords": "crear plubot, asistente, fábrica de bots"
    },
    {
        "category": "creacion_bots",
        "question": "¿Qué personalidades puedo elegir?",
        "answer": "Formal, amigable, motivacional, sabio y futurista. Próximamente más opciones.",
        "keywords": "personalidad, tipos, estilo bot"
    },
    {
        "category": "flujos_nodos",
        "question": "¿Qué es un flujo de nodos?",
        "answer": "Es un diagrama visual donde conectas bloques como mensajes, decisiones y acciones para automatizar respuestas y tareas.",
        "keywords": "flujo, nodos, automatización, diagrama"
    },
    {
        "category": "flujos_nodos",
        "question": "¿Cuáles nodos puedo usar?",
        "answer": "Mensaje, Decisión, Acción, Espera, Inicio y Final. Puedes combinarlos para crear flujos conversacionales inteligentes.",
        "keywords": "nodos, tipos, flujo, bot"
    },
    {
        "category": "integraciones",
        "question": "¿Con qué herramientas se puede conectar Plubot?",
        "answer": "Con WhatsApp, Instagram, Stripe, MercadoPago, Notion, Trello, Mailchimp, Google Sheets y más.",
        "keywords": "integraciones, apps, whatsapp, stripe"
    },
    {
        "category": "integraciones",
        "question": "¿Cómo conecto WhatsApp a Plubot?",
        "answer": "Desde el Marketplace, desbloquea el poder de WhatsApp y sigue las instrucciones para vincular tu cuenta empresarial vía Twilio o 360dialog.",
        "keywords": "conectar whatsapp, poder, integración"
    }
]

def load_knowledge_to_plubot():
    """Carga el conocimiento sobre Plubot a la base de datos"""
    try:
        payload = {
            "items": plubot_knowledge
        }
        
        response = requests.post(BULK_ADD_URL, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Éxito: {result['message']}")
            return True
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error al cargar el conocimiento: {str(e)}")
        return False

if __name__ == "__main__":
    print("Cargando base de conocimiento para Byte Embajador...")
    success = load_knowledge_to_plubot()
    if success:
        print("La base de conocimiento se ha cargado exitosamente.")
    else:
        print("Hubo un problema al cargar la base de conocimiento.")